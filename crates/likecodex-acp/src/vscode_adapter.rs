//! VS Code / Cursor LSP adapter for ACP.
//!
//! Bridges the ACP JSON-RPC protocol to the VS Code Language Server Protocol (LSP)
//! custom extension mechanism. This allows VS Code and Cursor extensions to
//! communicate with LikeCodex through standard LSP channels.
//!
//! The adapter translates between ACP notifications/methods and LSP custom
//! `window/showMessage`, `workspace/configuration`, and custom method calls.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::{debug, info, warn};

use crate::protocol::{
    AgentCapabilities, AuthMethod, ContentBlock, Implementation, InitializeParams,
    InitializeResult, ModelInfo, SessionConfigOption, SessionInfo, SessionNewParams,
    SessionNewResult, SessionPromptResult, StopReason, PROTOCOL_VERSION,
};
use crate::server::{Conn, RpcErrorBox};

/// VS Code LSP method names for ACP integration.
mod lsp_methods {
    /// Custom initialize: `workspace/executeCommand` with command `likecodex.initialize`.
    pub const INITIALIZE: &str = "likecodex.initialize";
    /// Custom session/new.
    pub const SESSION_NEW: &str = "likecodex.session.new";
    /// Custom session/prompt.
    pub const SESSION_PROMPT: &str = "likecodex.session.prompt";
    /// Custom session/list.
    pub const SESSION_LIST: &str = "likecodex.session.list";
    /// Custom session/close.
    pub const SESSION_CLOSE: &str = "likecodex.session.close";
    /// Custom notification: agent message chunk.
    pub const AGENT_MESSAGE: &str = "likecodex/agentMessage";
    /// Custom notification: tool call.
    pub const TOOL_CALL: &str = "likecodex/toolCall";
    /// Custom notification: tool result.
    pub const TOOL_RESULT: &str = "likecodex/toolResult";
    /// Custom notification: error.
    pub const ERROR: &str = "likecodex/error";
}

/// LSP adapter state for VS Code / Cursor integration.
#[derive(Debug, Clone)]
pub struct VSCodeAdapter {
    /// ACP connection to use for communication.
    conn: Arc<Conn>,
    /// Active sessions: session_id -> metadata
    active_sessions: Arc<Mutex<HashMap<String, SessionInfo>>>,
    /// Server capabilities
    capabilities: AgentCapabilities,
    /// Server info
    server_info: Implementation,
}

impl VSCodeAdapter {
    pub fn new(conn: Arc<Conn>) -> Self {
        Self {
            conn,
            active_sessions: Arc::new(Mutex::new(HashMap::new())),
            capabilities: AgentCapabilities::default(),
            server_info: Implementation {
                name: "likecodex-acp".to_string(),
                version: env!("CARGO_PKG_VERSION").to_string(),
            },
        }
    }

    /// Handle an LSP `workspace/executeCommand` call dispatched by the VS Code extension.
    /// The `command` field contains the ACP method name prefixed with `likecodex.`.
    pub async fn handle_execute_command(
        &self,
        command: &str,
        arguments: Vec<serde_json::Value>,
    ) -> Result<serde_json::Value, RpcErrorBox> {
        let params = arguments.into_iter().next().unwrap_or(serde_json::Value::Null);

        match command {
            lsp_methods::INITIALIZE => self.handle_initialize(params).await,
            lsp_methods::SESSION_NEW => self.handle_session_new(params).await,
            lsp_methods::SESSION_PROMPT => self.handle_session_prompt(params).await,
            lsp_methods::SESSION_LIST => self.handle_session_list().await,
            lsp_methods::SESSION_CLOSE => self.handle_session_close(params).await,
            _ => Err(RpcErrorBox::new(
                -32601,
                format!("unknown LSP command: {command}"),
            )),
        }
    }

    /// Register all LSP handlers on the ACP connection.
    ///
    /// This installs notification handlers that forward LSP custom notifications
    /// to the connected editor.
    pub async fn register_handlers(&self) {
        // agent message notification
        self.conn
            .handle_notify(
                lsp_methods::AGENT_MESSAGE,
                Arc::new(move |params| {
                    Box::pin(async move {
                        debug!(?params, "agent message notification");
                    })
                }),
            )
            .await;

        // tool call notification
        self.conn
            .handle_notify(
                lsp_methods::TOOL_CALL,
                Arc::new(move |params| {
                    Box::pin(async move {
                        debug!(?params, "tool call notification");
                    })
                }),
            )
            .await;

        // tool result notification
        self.conn
            .handle_notify(
                lsp_methods::TOOL_RESULT,
                Arc::new(move |params| {
                    Box::pin(async move {
                        debug!(?params, "tool result notification");
                    })
                }),
            )
            .await;
    }

    /// Emit a notification to the VS Code client via LSP `window/showMessage` or custom method.
    pub fn emit_agent_message(&self, session_id: &str, content: &str) {
        let notification = serde_json::json!({
            "jsonrpc": "2.0",
            "method": lsp_methods::AGENT_MESSAGE,
            "params": {
                "session_id": session_id,
                "content": content,
            }
        });
        self.conn.notify(lsp_methods::AGENT_MESSAGE, &notification);
    }

    // ── Handler implementations ─────────────────────────────────

    async fn handle_initialize(
        &self,
        params: serde_json::Value,
    ) -> Result<serde_json::Value, RpcErrorBox> {
        let _init: InitializeParams = serde_json::from_value(params)
            .map_err(|e| RpcErrorBox::new(-32602, format!("invalid params: {e}")))?;

        let result = InitializeResult {
            protocol_version: PROTOCOL_VERSION,
            server_info: self.server_info.clone(),
            capabilities: self.capabilities.clone(),
            auth_methods: None,
        };

        serde_json::to_value(result)
            .map_err(|e| RpcErrorBox::new(-32603, format!("serialization error: {e}")))
    }

    async fn handle_session_new(
        &self,
        params: serde_json::Value,
    ) -> Result<serde_json::Value, RpcErrorBox> {
        let p: SessionNewParams = serde_json::from_value(params)
            .map_err(|e| RpcErrorBox::new(-32602, format!("invalid params: {e}")))?;

        let session_id = uuid::Uuid::new_v4().to_string();
        let now = chrono::Utc::now().to_rfc3339();

        let info = SessionInfo {
            id: session_id.clone(),
            cwd: p.cwd.clone(),
            title: None,
            model: p.model.clone(),
            created_at: Some(now.clone()),
            updated_at: Some(now),
        };

        {
            let mut sessions = self.active_sessions.lock().await;
            sessions.insert(session_id.clone(), info);
        }

        let result = SessionNewResult {
            session_id,
            models: vec![
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
            ],
            config_options: vec![SessionConfigOption {
                id: "approval_mode".to_string(),
                name: Some("Approval Mode".to_string()),
                option_type: "select".to_string(),
                default: Some(serde_json::Value::String("auto".to_string())),
                options: Some(vec![]),
            }],
        };

        serde_json::to_value(result)
            .map_err(|e| RpcErrorBox::new(-32603, format!("serialization error: {e}")))
    }

    async fn handle_session_prompt(
        &self,
        params: serde_json::Value,
    ) -> Result<serde_json::Value, RpcErrorBox> {
        // Validate that the session exists
        let session_id = params
            .get("session_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| RpcErrorBox::new(-32602, "missing session_id"))?;

        {
            let sessions = self.active_sessions.lock().await;
            if !sessions.contains_key(session_id) {
                return Err(RpcErrorBox::new(-32602, "session not found"));
            }
        }

        let result = SessionPromptResult {
            stop_reason: StopReason::EndTurn,
        };

        serde_json::to_value(result)
            .map_err(|e| RpcErrorBox::new(-32603, format!("serialization error: {e}")))
    }

    async fn handle_session_list(&self) -> Result<serde_json::Value, RpcErrorBox> {
        let sessions = {
            let sessions = self.active_sessions.lock().await;
            sessions.values().cloned().collect::<Vec<_>>()
        };

        serde_json::to_value(sessions)
            .map_err(|e| RpcErrorBox::new(-32603, format!("serialization error: {e}")))
    }

    async fn handle_session_close(
        &self,
        params: serde_json::Value,
    ) -> Result<serde_json::Value, RpcErrorBox> {
        let session_id = params
            .get("session_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| RpcErrorBox::new(-32602, "missing session_id"))?;

        {
            let mut sessions = self.active_sessions.lock().await;
            sessions.remove(session_id);
        }

        Ok(serde_json::Value::Bool(true))
    }
}

/// Build the LSP server capabilities JSON snippet indicating ACP support.
/// This is sent during LSP initialisation in the `ServerCapabilities`'s
/// `experimental` field.
pub fn lsp_server_capabilities() -> serde_json::Value {
    serde_json::json!({
        "likecodex": {
            "version": PROTOCOL_VERSION,
            "capabilities": {
                "load_session": false,
                "list_sessions": true,
                "close_session": true,
                "embedded_context": true,
            },
            "commands": [
                "likecodex.initialize",
                "likecodex.session.new",
                "likecodex.session.prompt",
                "likecodex.session.list",
                "likecodex.session.close",
            ],
            "notifications": [
                "likecodex/agentMessage",
                "likecodex/toolCall",
                "likecodex/toolResult",
                "likecodex/error",
            ],
        }
    })
}
