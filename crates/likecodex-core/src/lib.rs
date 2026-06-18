pub mod config;
pub mod events;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// A single task assigned to the agent.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    pub id: String,
    pub parent_id: Option<String>,
    pub description: String,
    pub status: TaskStatus,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub metadata: HashMap<String, serde_json::Value>,
}

impl Task {
    pub fn new(description: impl Into<String>) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4().to_string(),
            parent_id: None,
            description: description.into(),
            status: TaskStatus::Pending,
            created_at: now,
            updated_at: now,
            metadata: HashMap::new(),
        }
    }

    pub fn with_parent(mut self, parent_id: impl Into<String>) -> Self {
        self.parent_id = Some(parent_id.into());
        self
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum TaskStatus {
    Pending,
    Planning,
    Running,
    AwaitingPermission,
    Completed,
    Failed,
    Cancelled,
}

/// A tool call issued by the model.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCall {
    pub id: String,
    pub name: String,
    pub arguments: serde_json::Value,
}

/// The result of executing a tool call.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolResult {
    pub call_id: String,
    pub success: bool,
    pub output: String,
    pub metadata: HashMap<String, serde_json::Value>,
}

/// A permission request shown to the user before a sensitive action.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PermissionRequest {
    pub id: String,
    pub action_type: String,
    pub description: String,
    pub command: Option<String>,
    pub path: Option<String>,
}

/// Possible responses to a permission request.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PermissionResponse {
    Allow,
    AllowOnce,
    Deny,
    DenyOnce,
}

/// A message in the agent conversation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: Role,
    pub content: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tool_calls: Option<Vec<ToolCall>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tool_call_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    System,
    User,
    Assistant,
    Tool,
}

/// A plan produced by the planner.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Plan {
    pub task_id: String,
    pub steps: Vec<PlanStep>,
    pub reasoning: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlanStep {
    pub id: String,
    pub description: String,
    pub status: StepStatus,
    pub depends_on: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Default)]
#[serde(rename_all = "snake_case")]
pub enum StepStatus {
    #[default]
    Pending,
    InProgress,
    Completed,
    Failed,
    Skipped,
}

#[cfg(test)]
mod tests {
    use crate::config::Config;
    use crate::events::Event;

    #[test]
    fn redacts_api_key() {
        let mut cfg = Config::default();
        cfg.llm.api_key = Some("secret".to_string());
        cfg.server.api_token = Some("token".to_string());
        let redacted = cfg.redacted();
        assert_eq!(redacted.llm.api_key.as_deref(), Some("***"));
        assert_eq!(redacted.server.api_token.as_deref(), Some("***"));
    }

    #[test]
    fn event_serializes_adjacent_tag() {
        let event = Event::StreamChunk {
            task_id: "t1".to_string(),
            content: "hello".to_string(),
        };
        let json = serde_json::to_string(&event).unwrap();
        assert!(json.contains("\"type\":\"stream_chunk\""));
        assert!(json.contains("\"payload\""));
    }
}
