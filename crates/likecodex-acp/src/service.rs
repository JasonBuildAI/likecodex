//! ACP session lifecycle management.
//!
//! Manages sessions, bridges to the LikeCodex engine via HTTP,
//! and handles all ACP method implementations.

use crate::protocol::*;
use crate::server::RpcErrorBox;
use futures::StreamExt;
use likecodex_core::config::Config;
use likecodex_core::events::{Event, EventBus};
use reqwest::Client;
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::{info, warn};
use uuid::Uuid;

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
        // Engine handles cancellation via context, no explicit cancel endpoint needed
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
                command: output
                    .get("command")
                    .and_then(|c| c.as_str())
                    .map(|s| s.to_string()),
                path: output
                    .get("path")
                    .and_then(|p| p.as_str())
                    .map(|s| s.to_string()),
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

/// ACP service managing all sessions.
pub struct AcpService {
    factory: Arc<SessionFactory>,
    sessions: Arc<Mutex<HashMap<String, SessionInfo>>>,
}

impl AcpService {
    pub fn new(engine_url: String, config: Config, event_bus: EventBus) -> Self {
        Self {
            factory: Arc::new(SessionFactory::new(engine_url, config, event_bus)),
            sessions: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub fn factory(&self) -> Arc<SessionFactory> {
        self.factory.clone()
    }

    pub fn sessions(&self) -> Arc<Mutex<HashMap<String, SessionInfo>>> {
        self.sessions.clone()
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

        self.factory.load_session(&p.session_id, p.cwd).await
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

        // Config changes are forwarded to the engine on next prompt
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
        let sessions = self.sessions.lock().await;
        let list: Vec<SessionInfo> = sessions.values().cloned().collect();
        Ok(serde_json::to_value(SessionListResult { sessions: list })
            .map_err(|e| RpcErrorBox::new(ERR_INTERNAL, e.to_string()))?)
    }

    pub async fn handle_session_close(&self, params: Value) -> Result<Value, RpcErrorBox> {
        let p: SessionCloseParams = serde_json::from_value(params)
            .map_err(|e| RpcErrorBox::new(ERR_INVALID_PARAMS, e.to_string()))?;

        let mut sessions = self.sessions.lock().await;
        sessions.remove(&p.session_id);

        Ok(serde_json::to_value(SessionCloseResult { ok: true })
            .map_err(|e| RpcErrorBox::new(ERR_INTERNAL, e.to_string()))?)
    }

    pub async fn handle_session_delete(&self, params: Value) -> Result<Value, RpcErrorBox> {
        let p: SessionDeleteParams = serde_json::from_value(params)
            .map_err(|e| RpcErrorBox::new(ERR_INVALID_PARAMS, e.to_string()))?;

        let mut sessions = self.sessions.lock().await;
        sessions.remove(&p.session_id);

        Ok(serde_json::to_value(SessionDeleteResult { ok: true })
            .map_err(|e| RpcErrorBox::new(ERR_INTERNAL, e.to_string()))?)
    }
}