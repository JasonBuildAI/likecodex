/// ── Request / Response DTOs ────────────────────────────────────────

#[derive(serde::Deserialize)]
pub struct CreateTaskRequest {
    pub prompt: String,
    #[serde(default)]
    pub session_id: Option<String>,
    #[serde(default)]
    pub no_tools: bool,
    #[serde(default)]
    pub agent_mode: Option<String>,
}

#[derive(serde::Deserialize)]
pub struct PlanRequest {
    pub prompt: String,
}

#[derive(serde::Deserialize)]
pub struct ExecuteRequest {
    pub command: String,
    #[serde(default)]
    pub working_dir: Option<String>,
}

#[derive(serde::Deserialize)]
pub struct PermissionRespondRequest {
    pub approved: bool,
    #[serde(default)]
    pub grant_scope: Option<String>,
}

#[derive(serde::Deserialize)]
pub struct AskRespondRequest {
    pub answers: serde_json::Value,
}

#[derive(serde::Deserialize)]
pub struct RewindCheckpointRequest {
    pub checkpoint_id: Option<String>,
    #[serde(default)]
    pub mode: Option<String>,
    #[serde(default)]
    pub session_id: Option<String>,
}

#[derive(serde::Deserialize)]
pub struct IndexSearchQuery {
    pub pattern: String,
}

#[derive(serde::Deserialize)]
pub struct ApproveRequest {
    pub request_id: String,
    pub approved: bool,
    #[serde(default)]
    pub grant_scope: Option<String>,
}

#[derive(serde::Deserialize)]
pub struct SessionIdRequest {
    pub session_id: String,
}

#[derive(serde::Deserialize)]
pub struct CompactRequest {
    pub session_id: String,
    #[serde(default)]
    pub focus: Option<String>,
}

#[derive(serde::Deserialize)]
pub struct NewSessionRequest {
    #[serde(default)]
    pub cwd: Option<String>,
}

#[derive(serde::Deserialize)]
pub struct RewindRequest {
    pub session_id: String,
    #[serde(default)]
    pub checkpoint_id: Option<String>,
    #[serde(default)]
    pub mode: Option<String>,
}

#[derive(serde::Deserialize)]
pub struct ForkRequest {
    pub session_id: String,
    #[serde(default)]
    pub label: Option<String>,
}

#[derive(serde::Deserialize)]
pub struct SummarizeRequest {
    pub session_id: String,
}

#[derive(serde::Deserialize)]
pub struct SetApprovalModeRequest {
    pub session_id: String,
    pub mode: String,
}

#[derive(serde::Deserialize)]
pub struct AnswerRequest {
    pub request_id: String,
    pub answers: serde_json::Value,
}
