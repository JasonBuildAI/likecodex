//! ACP session lifecycle management with SQLite persistence.
//!
//! Manages sessions, bridges to the LikeCodex engine via HTTP,
//! and handles all ACP method implementations.

use crate::protocol::*;
use crate::server::RpcErrorBox;
use futures::StreamExt;
use likecodex_core::config::Config;
use likecodex_core::events::{Event, EventBus};
use likecodex_core::PermissionResponse;
use reqwest::Client;
use rusqlite::Connection;
use serde_json::Value;
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::{info, warn};
use uuid::Uuid;

// ── SQLite-backed session store ─────────────────────────────────

/// Persistent session store backed by a local SQLite database.
pub struct SessionStore {
    conn: Mutex<Connection>,
}

impl SessionStore {
    /// Open or create the session database at the given path.
    pub fn new(db_path: &std::path::Path) -> Result<Self, rusqlite::Error> {
        // Ensure parent directory exists
        if let Some(parent) = db_path.parent() {
            std::fs::create_dir_all(parent).ok();
        }

        let conn = Connection::open(db_path)?;
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                cwd         TEXT NOT NULL DEFAULT '',
                title       TEXT,
                model       TEXT,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );",
        )?;
        Ok(Self {
            conn: Mutex::new(conn),
        })
    }

    /// Open with a sensible default path.
    pub fn default_path() -> PathBuf {
        std::env::var("LIKECODEX_DATA_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from(".likecodex/acp"))
            .join("sessions.db")
    }

    /// Insert a new session record.
    pub async fn insert(&self, info: &SessionInfo) -> Result<(), rusqlite::Error> {
        let conn = self.conn.lock().await;
        conn.execute(
            "INSERT INTO sessions (id, cwd, title, model, created_at, updated_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            rusqlite::params![
                info.id,
                info.cwd.as_deref().unwrap_or(""),
                info.title,
                info.model,
                info.created_at,
                info.updated_at,
            ],
        )?;
        Ok(())
    }

    /// Retrieve a session by ID.
    pub async fn get(&self, id: &str) -> Result<Option<SessionInfo>, rusqlite::Error> {
        let conn = self.conn.lock().await;
        let mut stmt = conn.prepare(
            "SELECT id, cwd, title, model, created_at, updated_at FROM sessions WHERE id = ?1",
        )?;
        let mut rows = stmt.query(rusqlite::params![id])?;
        if let Some(row) = rows.next()? {
            Ok(Some(SessionInfo {
                id: row.get(0)?,
                cwd: row.get::<_, String>(1).ok().filter(|s| !s.is_empty()),
                title: row.get(2)?,
                model: row.get(3)?,
                created_at: row.get(4)?,
                updated_at: row.get(5)?,
            }))
        } else {
            Ok(None)
        }
    }

    /// List all sessions.
    pub async fn list(&self) -> Result<Vec<SessionInfo>, rusqlite::Error> {
        let conn = self.conn.lock().await;
        let mut stmt = conn.prepare(
            "SELECT id, cwd, title, model, created_at, updated_at FROM sessions ORDER BY updated_at DESC",
        )?;
        let rows = stmt.query_map([], |row| {
            Ok(SessionInfo {
                id: row.get(0)?,
                cwd: row.get::<_, String>(1).ok().filter(|s| !s.is_empty()),
                title: row.get(2)?,
                model: row.get(3)?,
                created_at: row.get(4)?,
                updated_at: row.get(5)?,
            })
        })?;
        let mut sessions = Vec::new();
        for row in rows {
            sessions.push(row?);
        }
        Ok(sessions)
    }

    /// Update a session's metadata.
    pub async fn update(&self, info: &SessionInfo) -> Result<(), rusqlite::Error> {
        let conn = self.conn.lock().await;
        conn.execute(
            "UPDATE sessions SET cwd = ?1, title = ?2, model = ?3, updated_at = ?4 WHERE id = ?5",
            rusqlite::params![
                info.cwd.as_deref().unwrap_or(""),
                info.title,
                info.model,
                info.updated_at,
                info.id,
            ],
        )?;
        Ok(())
    }

    /// Delete a session by ID.
    pub async fn delete(&self, id: &str) -> Result<(), rusqlite::Error> {
        let conn = self.conn.lock().await;
        conn.execute("DELETE FROM sessions WHERE id = ?1", rusqlite::params![id])?;
        Ok(())
    }
}

// ── Session Factory ─────────────────────────────────────────────

/// Factory for creating session controllers.
/// Each session is backed by the LikeCodex engine via HTTP.
pub struct SessionFactory {
    engine_url: String,
    client: Client,
    event_bus: EventBus,
    config: Config,
}

impl SessionFactory {
    pub fn new(engine_url: String, config: Config, event_bus: EventBus) -> Self {
        Self {
            engine_url,
            client: Client::new(),
            event_bus,
            config,
        }
    }

    pub fn event_bus(&self) -> &EventBus {
        &self.event_bus
    }

    pub async fn health_check(&self) -> Result<(), String> {
        let url = format!("{}/health", self.engine_url);
        self.client
            .get(&url)
            .send()
            .await
            .map_err(|e| format!("engine unreachable: {e}"))?;
        Ok(())
    }

    pub async fn create_session(
        &self,
        cwd: Option<String>,
        _mcp_servers: &[MCPServerSpec],
        model: Option<String>,
    ) -> Result<SessionInfo, RpcErrorBox> {
        let session_id = Uuid::new_v4().to_string();
        let cwd = cwd.unwrap_or_else(|| ".".to_string());
        let model = model.unwrap_or_else(|| self.config.llm.model.clone());

        info!(
            session_id = %session_id,
            cwd = %cwd,
            model = %model,
            "ACP session created"
        );

        Ok(SessionInfo {
            id: session_id,
            cwd: Some(cwd),
            title: None,
            created_at: Some(chrono::Utc::now().to_rfc3339()),
            updated_at: Some(chrono::Utc::now().to_rfc3339()),
            model: Some(model),
        })
    }

    pub async fn send_prompt(
        &self,
        session_id: &str,
        prompt: &str,
        no_tools: bool,
    ) -> Result<StopReason, RpcErrorBox> {
        let url = format!("{}/chat", self.engine_url);
        let body = serde_json::json!({
            "prompt": prompt,
            "session_id": session_id,
            "no_tools": no_tools,
        });

        let response = self
            .client
            .post(&url)
            .json(&body)
            .send()
            .await
            .map_err(|e| RpcErrorBox::new(ERR_INTERNAL, format!("engine error: {e}")))?;

        if !response.status().is_success() {
            let status = response.status().as_u16();
            return Err(RpcErrorBox::new(
                ERR_INTERNAL,
                format!("engine returned status {status}"),
            ));
        }

        let mut stream = response.bytes_stream();
        let mut has_error = false;

        while let Some(chunk) = stream.next().await {
            match chunk {
                Ok(bytes) => {
                    let text = String::from_utf8_lossy(&bytes);
                    for line in text.lines() {
                        let line = line.trim();
                        if let Some(data) = line.strip_prefix("data: ") {
                            if data == "[DONE]" {
                                break;
                            }
                            if let Ok(output) = serde_json::from_str::<Value>(data) {
                                let event = map_engine_output_to_event(session_id, &output);
                                if let Err(e) = self.event_bus.emit(event) {
                                    warn!("event bus emit failed: {e}");
                                }
                            }
                        }
                    }
                }
                Err(e) => {
                    warn!("stream error: {e}");
                    has_error = true;
                    break;
                }
            }
        }

        if has_error {
            Ok(StopReason::Error)
        } else {
            Ok(StopReason::EndTurn)
        }
    }

    pub async fn cancel_session(&self, session_id: &str) -> Result<(), RpcErrorBox> {
        info!(session_id = %session_id, "ACP session cancel requested");
        Ok(())
    }

    pub async fn load_session(
        &self,
        session_id: &str,
        _cwd: Option<String>,
    ) -> Result<SessionLoadResult, RpcErrorBox> {
        let url = format!("{}/sessions/{session_id}/events", self.engine_url);
        let response = self
            .client
            .get(&url)
            .send()
            .await
            .map_err(|e| RpcErrorBox::new(ERR_INTERNAL, format!("engine error: {e}")))?;

        if response.status().as_u16() == 404 {
            return Err(RpcErrorBox::new(ERR_INVALID_PARAMS, "session not found"));
        }

        Ok(SessionLoadResult {
            session_id: session_id.to_string(),
            models: get_available_models(),
            config_options: get_config_options(),
        })
    }

    /// Emit a permission response event back to the engine.
    pub fn emit_permission_response(
        &self,
        task_id: &str,
        request_id: &str,
        response: PermissionResponse,
    ) {
        let event = Event::PermissionResponded {
            task_id: task_id.to_string(),
            request_id: request_id.to_string(),
            response,
        };
        if let Err(e) = self.event_bus.emit(event) {
            warn!("failed to emit permission response: {e}");
        }
    }
}

/// Map engine SSE output to an Event.
fn map_engine_output_to_event(task_id: &str, output: &Value) -> Event {
    let event_type = output.get("type").and_then(|t| t.as_str()).unwrap_or("");

    match event_type {
        "assistant" | "delta" => Event::StreamChunk {
            task_id: task_id.to_string(),
            content: output
                .get("content")
                .and_then(|c| c.as_str())
                .unwrap_or("")
                .to_string(),
        },
        "tool_call" | "tool_dispatch" => {
            let tool_calls = output.get("tool_calls").and_then(|t| t.as_array());
            if let Some(tcs) = tool_calls {
                if let Some(tc) = tcs.first() {
                    return Event::ToolCallRequested {
                        task_id: task_id.to_string(),
                        call: likecodex_core::ToolCall {
                            id: tc
                                .get("id")
                                .and_then(|i| i.as_str())
                                .unwrap_or("")
                                .to_string(),
                            name: tc
                                .get("function")
                                .and_then(|f| f.get("name"))
                                .and_then(|n| n.as_str())
                                .unwrap_or("")
                                .to_string(),
                            arguments: tc
                                .get("function")
                                .and_then(|f| f.get("arguments"))
                                .cloned()
                                .unwrap_or(Value::Null),
                        },
                    };
                }
            }
            Event::StreamChunk {
                task_id: task_id.to_string(),
                content: String::new(),
            }
        }
        "tool_result" => Event::ToolCallCompleted {
            task_id: task_id.to_string(),
            result: likecodex_core::ToolResult {
                call_id: output
                    .get("call_id")
                    .and_then(|c| c.as_str())
                    .unwrap_or("")
                    .to_string(),
                success: output.get("error").is_none(),
                output: output
                    .get("content")
                    .and_then(|c| c.as_str())
                    .unwrap_or("")
                    .to_string(),
                metadata: HashMap::new(),
            },
        },
        "permission" => Event::PermissionRequested {
            task_id: task_id.to_string(),
            request: likecodex_core::PermissionRequest {
                id: output
                    .get("request_id")
                    .and_then(|r| r.as_str())
                    .unwrap_or("")
                    .to_string(),
                action_type: output
                    .get("tool_name")
                    .and_then(|t| t.as_str())
                    .unwrap_or("")
                    .to_string(),
                description: output
                    .get("description")
                    .and_then(|d| d.as_str())
                    .unwrap_or("")
                    .to_string(),
                command: output.get("command").and_then(|c| c.as_str()).map(|s| s.to_string()),
                path: output.get("path").and_then(|p| p.as_str()).map(|s| s.to_string()),
            },
        },
        "error" => Event::Error {
            task_id: Some(task_id.to_string()),
            message: output
                .get("content")
                .and_then(|c| c.as_str())
                .unwrap_or("unknown error")
                .to_string(),
        },
        "reasoning" => Event::ReasoningDelta {
            task_id: task_id.to_string(),
            content: output
                .get("content")
                .and_then(|c| c.as_str())
                .unwrap_or("")
                .to_string(),
        },
        _ => Event::StreamChunk {
            task_id: task_id.to_string(),
            content: output
                .get("content")
                .and_then(|c| c.as_str())
                .unwrap_or("")
                .to_string(),
        },
    }
}

/// Get available models from config.
fn get_available_models() -> Vec<ModelInfo> {
    vec![
        ModelInfo {
            id: "deepseek-v4-flash".to_string(),
            name: Some("DeepSeek V4 Flash".to_string()),
            description: Some("Fast execution model".to_string()),
        },
        ModelInfo {
            id: "deepseek-v4-pro".to_string(),
            name: Some("DeepSeek V4 Pro".to_string()),
            description: Some("Planning and complex reasoning model".to_string()),
        },
    ]
}

/// Get available session config options.
fn get_config_options() -> Vec<SessionConfigOption> {
    vec![
        SessionConfigOption {
            id: "model".to_string(),
            name: Some("Model".to_string()),
            option_type: "select".to_string(),
            default: Some(Value::String("deepseek-v4-flash".to_string())),
            options: Some(vec![
                SessionConfigSelectOption {
                    value: Value::String("deepseek-v4-flash".to_string()),
                    label: "DeepSeek V4 Flash".to_string(),
                },
                SessionConfigSelectOption {
                    value: Value::String("deepseek-v4-pro".to_string()),
                    label: "DeepSeek V4 Pro".to_string(),
                },
            ]),
        },
        SessionConfigOption {
            id: "approval_mode".to_string(),
            name: Some("Approval Mode".to_string()),
            option_type: "select".to_string(),
            default: Some(Value::String("auto".to_string())),
            options: Some(vec![
                SessionConfigSelectOption {
                    value: Value::String("read-only".to_string()),
                    label: "Read Only".to_string(),
                },
                SessionConfigSelectOption {
                    value: Value::String("auto".to_string()),
                    label: "Auto (Ask for writes)".to_string(),
                },
                SessionConfigSelectOption {
                    value: Value::String("yolo".to_string()),
                    label: "YOLO (Auto approve all)".to_string(),
                },
            ]),
        },
    ]
}

// ── ACP Service ────────────────────────────────────────────────

/// ACP service managing all sessions with SQLite persistence.
pub struct AcpService {
    factory: Arc<SessionFactory>,
    sessions: Arc<Mutex<HashMap<String, SessionInfo>>>,
    store: Arc<SessionStore>,
    // Tracks pending permission request_ids by session_id:
    // session_id -> (request_id, task_id)
    pending_permissions: Arc<Mutex<HashMap<String, (String, String)>>>,
}

impl AcpService {
    pub async fn new(
        engine_url: String,
        config: Config,
        event_bus: EventBus,
        store: Option<SessionStore>,
    ) -> Self {
        let store = store.unwrap_or_else(|| {
            SessionStore::new(&SessionStore::default_path())
                .unwrap_or_else(|e| {
                    warn!("failed to open session store (sessions not persisted): {e}");
                    // Create in-memory fallback so the service still works
                    let tmp = std::env::temp_dir().join("likecodex-acp-fallback.db");
                    SessionStore::new(&tmp).expect("in-memory session store fallback failed")
                })
        });

        // Load existing sessions from DB into memory
        let loaded = store.list().await.unwrap_or_default();
        let mut sessions_map = HashMap::new();
        for s in loaded {
            sessions_map.insert(s.id.clone(), s);
        }
        info!(count = sessions_map.len(), "ACP sessions loaded from store");

        Self {
            factory: Arc::new(SessionFactory::new(engine_url, config, event_bus)),
            sessions: Arc::new(Mutex::new(sessions_map)),
            store: Arc::new(store),
            pending_permissions: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub fn factory(&self) -> Arc<SessionFactory> {
        self.factory.clone()
    }

    pub fn store(&self) -> Arc<SessionStore> {
        self.store.clone()
    }

    pub fn pending_permissions(&self) -> Arc<Mutex<HashMap<String, (String, String)>>> {
        self.pending_permissions.clone()
    }

    /// Record a pending permission request for a session.
    pub fn record_permission_request(&self, session_id: &str, request_id: &str, task_id: &str) {
        if let Ok(mut map) = self.pending_permissions.try_lock() {
            map.insert(session_id.to_string(), (request_id.to_string(), task_id.to_string()));
        }
    }

    // ── RPC method handlers ───────────────────────────────────

    pub async fn handle_initialize(&self, params: Value) -> Result<Value, RpcErrorBox> {
        let _init: InitializeParams = serde_json::from_value(params)
            .map_err(|e| RpcErrorBox::new(ERR_INVALID_PARAMS, e.to_string()))?;

        Ok(serde_json::to_value(InitializeResult {
            protocol_version: PROTOCOL_VERSION,
            server_info: Implementation {
                name: "likecodex-acp".to_string(),
                version: env!("CARGO_PKG_VERSION").to_string(),
            },
            capabilities: AgentCapabilities {
                load_session: true,
                list_sessions: true,
                resume_session: true,
                close_session: true,
                delete_session: true,
                embedded_context: true,
                mcp: Some(MCPCapabilities { http: true }),
                session: SessionCapabilities {
                    config_options: get_config_options(),
                },
                prompt: PromptCapabilities {
                    embedded_context: true,
                    image: false,
                },
            },
            auth_methods: None,
        })
        .map_err(|e| RpcErrorBox::new(ERR_INTERNAL, e.to_string()))?)
    }

    pub async fn handle_authenticate(&self, _params: Value) -> Result<Value, RpcErrorBox> {
        Ok(serde_json::to_value(AuthenticateResult { ok: true })
            .map_err(|e| RpcErrorBox::new(ERR_INTERNAL, e.to_string()))?)
    }

    pub async fn handle_session_new(&self, params: Value) -> Result<Value, RpcErrorBox> {
        let p: SessionNewParams = serde_json::from_value(params)
            .map_err(|e| RpcErrorBox::new(ERR_INVALID_PARAMS, e.to_string()))?;

        let session = self
            .factory
            .create_session(p.cwd, &p.mcp_servers, p.model)
            .await?;

        let session_id = session.id.clone();

        // Persist to SQLite
        if let Err(e) = self.store.insert(&session).await {
            warn!("failed to persist session {session_id}: {e}");
        }

        // Update in-memory cache
        {
            let mut sessions = self.sessions.lock().await;
            sessions.insert(session_id.clone(), session);
        }

        Ok(serde_json::to_value(SessionNewResult {
            session_id,
            models: get_available_models(),
            config_options: get_config_options(),
        })
        .map_err(|e| RpcErrorBox::new(ERR_INTERNAL, e.to_string()))?)
    }

    pub async fn handle_session_load(&self, params: Value) -> Result<Value, RpcErrorBox> {
        let p: SessionLoadParams = serde_json::from_value(params)
            .map_err(|e| RpcErrorBox::new(ERR_INVALID_PARAMS, e.to_string()))?;

        self.factory
            .load_session(&p.session_id, p.cwd)
            .await
            .map(|r| serde_json::to_value(r).unwrap_or_default())
    }

    pub async fn handle_session_resume(&self, params: Value) -> Result<Value, RpcErrorBox> {
        let p: SessionResumeParams = serde_json::from_value(params)
            .map_err(|e| RpcErrorBox::new(ERR_INVALID_PARAMS, e.to_string()))?;

        Ok(serde_json::to_value(SessionResumeResult {
            session_id: p.session_id,
        })
        .map_err(|e| RpcErrorBox::new(ERR_INTERNAL, e.to_string()))?)
    }

    pub async fn handle_session_prompt(&self, params: Value) -> Result<Value, RpcErrorBox> {
        let p: SessionPromptParams = serde_json::from_value(params)
            .map_err(|e| RpcErrorBox::new(ERR_INVALID_PARAMS, e.to_string()))?;

        let prompt = flatten_prompt(&p.prompt);
        let stop_reason = self
            .factory
            .send_prompt(&p.session_id, &prompt, p.no_tools)
            .await?;

        Ok(serde_json::to_value(SessionPromptResult { stop_reason })
            .map_err(|e| RpcErrorBox::new(ERR_INTERNAL, e.to_string()))?)
    }

    pub async fn handle_session_cancel(&self, params: Value) -> Result<Value, RpcErrorBox> {
        let p: SessionCancelParams = serde_json::from_value(params)
            .map_err(|e| RpcErrorBox::new(ERR_INVALID_PARAMS, e.to_string()))?;

        self.factory.cancel_session(&p.session_id).await?;
        Ok(Value::Null)
    }

    pub async fn handle_session_set_config_option(
        &self,
        params: Value,
    ) -> Result<Value, RpcErrorBox> {
        let _p: SetSessionConfigOptionParams = serde_json::from_value(params)
            .map_err(|e| RpcErrorBox::new(ERR_INVALID_PARAMS, e.to_string()))?;

        Ok(serde_json::to_value(SetSessionConfigOptionResult { ok: true })
            .map_err(|e| RpcErrorBox::new(ERR_INTERNAL, e.to_string()))?)
    }

    pub async fn handle_session_set_model(&self, params: Value) -> Result<Value, RpcErrorBox> {
        let _p: SetSessionModelParams = serde_json::from_value(params)
            .map_err(|e| RpcErrorBox::new(ERR_INVALID_PARAMS, e.to_string()))?;

        Ok(serde_json::to_value(SetSessionModelResult { ok: true })
            .map_err(|e| RpcErrorBox::new(ERR_INTERNAL, e.to_string()))?)
    }

    pub async fn handle_session_list(&self, _params: Value) -> Result<Value, RpcErrorBox> {
        // Query from persistent store to ensure fresh data
        let sessions = self.store.list().await.unwrap_or_else(|e| {
            warn!("failed to list sessions from store: {e}");
            vec![]
        });
        Ok(serde_json::to_value(SessionListResult { sessions })
            .map_err(|e| RpcErrorBox::new(ERR_INTERNAL, e.to_string()))?)
    }

    pub async fn handle_session_close(&self, params: Value) -> Result<Value, RpcErrorBox> {
        let p: SessionCloseParams = serde_json::from_value(params)
            .map_err(|e| RpcErrorBox::new(ERR_INVALID_PARAMS, e.to_string()))?;

        {
            let mut sessions = self.sessions.lock().await;
            sessions.remove(&p.session_id);
        }

        Ok(serde_json::to_value(SessionCloseResult { ok: true })
            .map_err(|e| RpcErrorBox::new(ERR_INTERNAL, e.to_string()))?)
    }

    pub async fn handle_session_delete(&self, params: Value) -> Result<Value, RpcErrorBox> {
        let p: SessionDeleteParams = serde_json::from_value(params)
            .map_err(|e| RpcErrorBox::new(ERR_INVALID_PARAMS, e.to_string()))?;

        // Remove from persistent store
        if let Err(e) = self.store.delete(&p.session_id).await {
            warn!("failed to delete session {} from store: {e}", p.session_id);
        }

        // Remove from in-memory cache
        {
            let mut sessions = self.sessions.lock().await;
            sessions.remove(&p.session_id);
        }

        Ok(serde_json::to_value(SessionDeleteResult { ok: true })
            .map_err(|e| RpcErrorBox::new(ERR_INTERNAL, e.to_string()))?)
    }

    /// Handle `session/request_permission` — processes the client's permission decision.
    pub async fn handle_request_permission(&self, params: Value) -> Result<Value, RpcErrorBox> {
        let p: PermissionRequestParams = serde_json::from_value(params)
            .map_err(|e| RpcErrorBox::new(ERR_INVALID_PARAMS, e.to_string()))?;

        // Determine outcome from the first option (client's selection)
        let outcome_str = p
            .options
            .first()
            .map(|o| o.kind.as_str())
            .unwrap_or("deny_once");

        // Determine the PermissionResponse
        let response = match outcome_str {
            "allow_once" => PermissionResponse::AllowOnce,
            "allow_always" | "allow_session" => PermissionResponse::Allow,
            "deny_once" => PermissionResponse::DenyOnce,
            "deny_always" => PermissionResponse::Deny,
            _ => PermissionResponse::DenyOnce,
        };

        // Look up the pending permission to get request_id and task_id
        let (request_id, task_id) = {
            let mut perms = self.pending_permissions.lock().await;
            perms.remove(&p.session_id).unwrap_or_else(|| {
                // Fallback if no pending permission found
                ("unknown".to_string(), p.session_id.clone())
            })
        };

        // Forward the response to the engine
        self.factory.emit_permission_response(&task_id, &request_id, response);

        // Determine outcome string for the result
        let outcome = match outcome_str {
            "allow_once" => "allow_once",
            "allow_always" => "allow_always",
            "allow_session" => "allow_session",
            "deny_once" => "deny_once",
            "deny_always" => "deny_always",
            _ => "deny_once",
        };

        Ok(serde_json::to_value(PermissionRequestResult {
            outcome: outcome.to_string(),
        })
        .map_err(|e| RpcErrorBox::new(ERR_INTERNAL, e.to_string()))?)
    }
}
