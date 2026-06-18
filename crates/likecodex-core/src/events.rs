use crate::{Message, PermissionRequest, PermissionResponse, Plan, Task, ToolCall, ToolResult};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use tokio::sync::broadcast;

/// All events emitted by the agent system.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "payload", rename_all = "snake_case")]
pub enum Event {
    TaskStarted(Task),
    TaskUpdated(Task),
    TaskCompleted(Task),
    PlanCreated(Plan),
    PlanUpdated(Plan),
    MessageAdded {
        task_id: String,
        message: Message,
    },
    ToolCallRequested {
        task_id: String,
        call: ToolCall,
    },
    ToolCallCompleted {
        task_id: String,
        result: ToolResult,
    },
    PermissionRequested {
        task_id: String,
        request: PermissionRequest,
    },
    PermissionResponded {
        task_id: String,
        response: PermissionResponse,
    },
    StreamChunk {
        task_id: String,
        content: String,
    },
    StreamFinished {
        task_id: String,
    },
    Error {
        task_id: Option<String>,
        message: String,
    },
    Log {
        timestamp: DateTime<Utc>,
        level: String,
        message: String,
    },
}

/// A broadcast bus for agent events.
#[derive(Debug, Clone)]
pub struct EventBus {
    sender: broadcast::Sender<Event>,
}

impl EventBus {
    pub fn new(capacity: usize) -> Self {
        let (sender, _) = broadcast::channel(capacity);
        Self { sender }
    }

    pub fn subscribe(&self) -> broadcast::Receiver<Event> {
        self.sender.subscribe()
    }

    pub fn emit(&self, event: Event) -> anyhow::Result<()> {
        let _ = self.sender.send(event);
        Ok(())
    }

    pub fn sender(&self) -> broadcast::Sender<Event> {
        self.sender.clone()
    }
}

impl Default for EventBus {
    fn default() -> Self {
        Self::new(1024)
    }
}
