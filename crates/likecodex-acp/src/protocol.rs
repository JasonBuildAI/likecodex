//! ACP v1 protocol wire types.
//!
//! Defines all JSON-RPC 2.0 request/response/notification types
//! for the Agent Client Protocol, as specified by the ACP standard.

use serde::{Deserialize, Serialize};

/// ACP protocol version supported by this implementation.
pub const PROTOCOL_VERSION: u32 = 1;

// ── JSON-RPC 2.0 framing ──────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RpcRequest {
    pub jsonrpc: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<serde_json::Value>,
    pub method: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub params: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RpcResponse {
    pub jsonrpc: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<RpcError>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RpcError {
    pub code: i32,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<serde_json::Value>,
}

// Standard JSON-RPC error codes
pub const ERR_PARSE: i32 = -32700;
pub const ERR_INVALID_REQUEST: i32 = -32600;
pub const ERR_METHOD_NOT_FOUND: i32 = -32601;
pub const ERR_INVALID_PARAMS: i32 = -32602;
pub const ERR_INTERNAL: i32 = -32603;

// ── initialize ────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InitializeParams {
    pub protocol_version: u32,
    #[serde(default)]
    pub client_info: Implementation,
    #[serde(default)]
    pub capabilities: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Implementation {
    pub name: String,
    pub version: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InitializeResult {
    pub protocol_version: u32,
    pub server_info: Implementation,
    pub capabilities: AgentCapabilities,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub auth_methods: Option<Vec<AuthMethod>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentCapabilities {
    #[serde(default)]
    pub load_session: bool,
    #[serde(default)]
    pub list_sessions: bool,
    #[serde(default)]
    pub resume_session: bool,
    #[serde(default)]
    pub close_session: bool,
    #[serde(default)]
    pub delete_session: bool,
    #[serde(default)]
    pub embedded_context: bool,
    #[serde(default)]
    pub mcp: Option<MCPCapabilities>,
    #[serde(default)]
    pub session: SessionCapabilities,
    #[serde(default)]
    pub prompt: PromptCapabilities,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SessionCapabilities {
    #[serde(default)]
    pub config_options: Vec<SessionConfigOption>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct PromptCapabilities {
    #[serde(default)]
    pub embedded_context: bool,
    #[serde(default)]
    pub image: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct MCPCapabilities {
    #[serde(default)]
    pub http: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthMethod {
    pub id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
}

// ── authenticate ──────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthenticateParams {
    pub method_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub token: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthenticateResult {
    pub ok: bool,
}

// ── session/new ───────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionNewParams {
    #[serde(default)]
    pub cwd: Option<String>,
    #[serde(default)]
    pub mcp_servers: Vec<MCPServerSpec>,
    #[serde(default)]
    pub model: Option<String>,
    #[serde(default)]
    pub config_options: Vec<SetSessionConfigOptionParams>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MCPServerSpec {
    pub name: String,
    #[serde(default)]
    pub command: Option<String>,
    #[serde(default)]
    pub args: Vec<String>,
    #[serde(default)]
    pub env: Vec<EnvVariable>,
    #[serde(default)]
    pub url: Option<String>,
    #[serde(default)]
    pub transport: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnvVariable {
    pub name: String,
    pub value: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionNewResult {
    pub session_id: String,
    #[serde(default)]
    pub models: Vec<ModelInfo>,
    pub config_options: Vec<SessionConfigOption>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelInfo {
    pub id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
}

// ── session/load ──────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionLoadParams {
    pub session_id: String,
    #[serde(default)]
    pub cwd: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionLoadResult {
    pub session_id: String,
    #[serde(default)]
    pub models: Vec<ModelInfo>,
    pub config_options: Vec<SessionConfigOption>,
}

// ── session/resume ────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionResumeParams {
    pub session_id: String,
    #[serde(default)]
    pub cwd: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionResumeResult {
    pub session_id: String,
}

// ── session/list ──────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionListParams {
    #[serde(default)]
    pub cwd: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionListResult {
    pub sessions: Vec<SessionInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionInfo {
    pub id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cwd: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub created_at: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub updated_at: Option<String>,
    #[serde(default)]
    pub model: Option<String>,
}

// ── session/close ─────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionCloseParams {
    pub session_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionCloseResult {
    pub ok: bool,
}

// ── session/delete ────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionDeleteParams {
    pub session_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionDeleteResult {
    pub ok: bool,
}

// ── session/prompt ────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionPromptParams {
    pub session_id: String,
    pub prompt: Vec<ContentBlock>,
    #[serde(default)]
    pub no_tools: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum ContentBlock {
    #[serde(rename = "text")]
    Text { text: String },
    #[serde(rename = "resource")]
    Resource { resource: ResourceContents },
    #[serde(rename = "resource_link")]
    ResourceLink { uri: String },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceContents {
    pub uri: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub text: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mime_type: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StopReason {
    EndTurn,
    Cancelled,
    Error,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionPromptResult {
    pub stop_reason: StopReason,
}

/// Flatten content blocks into a single text prompt.
pub fn flatten_prompt(blocks: &[ContentBlock]) -> String {
    blocks
        .iter()
        .map(|b| match b {
            ContentBlock::Text { text } => text.clone(),
            ContentBlock::Resource { resource } => {
                resource.text.clone().unwrap_or_else(|| resource.uri.clone())
            }
            ContentBlock::ResourceLink { uri } => uri.clone(),
        })
        .collect::<Vec<_>>()
        .join("\n")
}

// ── session/cancel ────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionCancelParams {
    pub session_id: String,
}

// ── session/set_config_option ─────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SetSessionConfigOptionParams {
    pub session_id: String,
    pub id: String,
    pub value: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SetSessionConfigOptionResult {
    pub ok: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionConfigOption {
    pub id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(rename = "type")]
    pub option_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub options: Option<Vec<SessionConfigSelectOption>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionConfigSelectOption {
    pub value: serde_json::Value,
    pub label: String,
}

// ── session/set_model ─────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SetSessionModelParams {
    pub session_id: String,
    pub model: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SetSessionModelResult {
    pub ok: bool,
}

// ── session/update (notification) ─────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "update_type")]
pub enum SessionUpdate {
    #[serde(rename = "agent_message_chunk")]
    AgentMessageChunk {
        session_id: String,
        content: Vec<ContentBlock>,
    },
    #[serde(rename = "agent_thought_chunk")]
    AgentThoughtChunk {
        session_id: String,
        content: Vec<ContentBlock>,
    },
    #[serde(rename = "user_message_chunk")]
    UserMessageChunk {
        session_id: String,
        content: Vec<ContentBlock>,
    },
    #[serde(rename = "tool_call")]
    ToolCall {
        session_id: String,
        tool_call_id: String,
        name: String,
        #[serde(default)]
        arguments: serde_json::Value,
        #[serde(default)]
        kind: Option<String>,
        #[serde(default)]
        subject: Option<String>,
    },
    #[serde(rename = "tool_call_update")]
    ToolCallUpdate {
        session_id: String,
        tool_call_id: String,
        status: String,
        #[serde(default)]
        content: Option<Vec<ContentBlock>>,
        #[serde(default)]
        truncated: bool,
    },
    #[serde(rename = "available_commands_update")]
    AvailableCommandsUpdate {
        session_id: String,
        commands: Vec<AvailableCommand>,
    },
    #[serde(rename = "config_option_update")]
    ConfigOptionUpdate {
        session_id: String,
        options: Vec<SessionConfigOption>,
    },
    #[serde(rename = "session_error")]
    SessionError {
        session_id: String,
        message: String,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AvailableCommand {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input: Option<AvailableCommandInput>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AvailableCommandInput {
    #[serde(rename = "type")]
    pub input_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub placeholder: Option<String>,
}

// ── session/request_permission ────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PermissionRequestParams {
    pub session_id: String,
    pub tool_call: PermissionToolCall,
    #[serde(default)]
    pub options: Vec<PermissionOption>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PermissionToolCall {
    pub name: String,
    #[serde(default)]
    pub arguments: serde_json::Value,
    #[serde(default)]
    pub subject: Option<String>,
    #[serde(default)]
    pub kind: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PermissionOption {
    pub kind: String,
    pub label: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PermissionRequestResult {
    pub outcome: String,
}

/// Permission outcome kinds
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PermissionOutcome {
    AllowOnce,
    AllowAlways,
    AllowSession,
    DenyOnce,
    DenyAlways,
}

impl PermissionOutcome {
    pub fn is_approved(&self) -> bool {
        matches!(self, Self::AllowOnce | Self::AllowAlways | Self::AllowSession)
    }

    pub fn grant_scope(&self) -> &str {
        match self {
            Self::AllowOnce => "once",
            Self::AllowAlways => "always",
            Self::AllowSession => "session",
            Self::DenyOnce => "once",
            Self::DenyAlways => "always",
        }
    }
}