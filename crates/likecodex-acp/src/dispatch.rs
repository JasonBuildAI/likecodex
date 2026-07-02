//! Event to ACP notification mapping.
//!
//! Converts LikeCodex internal events into ACP session/update
//! notifications for the connected editor/client.
//! Also provides registration helpers for permission handlers.

use crate::protocol::*;
use crate::server::{AsyncRequestHandler, Conn, RpcErrorBox};
use likecodex_core::events::Event;
use std::sync::Arc;
use tracing::{debug, warn};

/// Maximum characters for tool result content in ACP notifications.
const MAX_RESULT_CHARS: usize = 8000;

/// Maps a tool name to its ACP tool kind.
pub fn tool_kind_for(name: &str) -> &str {
    match name {
        n if n.starts_with("read_file")
            || n.starts_with("list_dir")
            || n == "ls" || n == "glob" =>
        {
            "read"
        }
        n if n.starts_with("grep")
            || n.starts_with("search")
            || n.starts_with("find")
            || n.starts_with("codegraph")
            || n == "code_index" =>
        {
            "search"
        }
        n if n.starts_with("edit_file")
            || n.starts_with("write_file")
            || n.starts_with("multi_edit")
            || n.starts_with("move_file")
            || n.starts_with("delete") =>
        {
            "edit"
        }
        n if n.starts_with("run_command")
            || n.starts_with("bash")
            || n.starts_with("git") =>
        {
            "execute"
        }
        _ => "other",
    }
}

/// Extract a subject string from tool arguments.
pub fn extract_subject(name: &str, args: &serde_json::Value) -> Option<String> {
    if name == "run_command" {
        return args
            .get("command")
            .and_then(|c| c.as_str())
            .map(|s| s.to_string());
    }
    for key in &["path", "file_path", "pattern"] {
        if let Some(v) = args.get(key).and_then(|a| a.as_str()) {
            return Some(v.to_string());
        }
    }
    None
}

/// Clip text to `MAX_RESULT_CHARS` (UTF-8 safe).
fn clip(text: &str) -> String {
    if text.len() <= MAX_RESULT_CHARS {
        return text.to_string();
    }
    let mut end = MAX_RESULT_CHARS;
    while end > 0 && !text.is_char_boundary(end) {
        end -= 1;
    }
    format!("{}...", &text[..end])
}

/// Build a text content block.
fn text_block(text: &str) -> ContentBlock {
    ContentBlock::Text {
        text: text.to_string(),
    }
}

/// An event sink that converts Events into ACP notifications.
pub struct UpdateSink {
    conn: Arc<Conn>,
    session_id: String,
}

impl UpdateSink {
    pub fn new(conn: Arc<Conn>, session_id: String) -> Self {
        Self { conn, session_id }
    }

    /// Emit an ACP session/update notification for the given event.
    pub fn emit(&self, event: &Event) {
        match event {
            Event::StreamChunk { content, .. } => {
                if !content.is_empty() {
                    self.send(&SessionUpdate::AgentMessageChunk {
                        session_id: self.session_id.clone(),
                        content: vec![text_block(content)],
                    });
                }
            }
            Event::ReasoningDelta { content, .. } => {
                if !content.is_empty() {
                    self.send(&SessionUpdate::AgentThoughtChunk {
                        session_id: self.session_id.clone(),
                        content: vec![text_block(content)],
                    });
                }
            }
            Event::ToolCallRequested { call, .. } => {
                let kind = tool_kind_for(&call.name);
                let subject = extract_subject(&call.name, &call.arguments);
                self.send(&SessionUpdate::ToolCall {
                    session_id: self.session_id.clone(),
                    tool_call_id: call.id.clone(),
                    name: call.name.clone(),
                    arguments: call.arguments.clone(),
                    kind: Some(kind.to_string()),
                    subject,
                });
            }
            Event::ToolCallCompleted { result, .. } => {
                let status = if result.success {
                    "completed"
                } else {
                    "failed"
                };
                let content = clip(&result.output);
                self.send(&SessionUpdate::ToolCallUpdate {
                    session_id: self.session_id.clone(),
                    tool_call_id: result.call_id.clone(),
                    status: status.to_string(),
                    content: Some(vec![text_block(&content)]),
                    truncated: result.output.len() > MAX_RESULT_CHARS,
                });
            }
            Event::Error { message, .. } => {
                self.send(&SessionUpdate::SessionError {
                    session_id: self.session_id.clone(),
                    message: message.clone(),
                });
            }
            Event::PlanModeChanged { active, reason, .. } => {
                let msg = if *active {
                    format!("[plan mode] {reason}")
                } else {
                    format!("[plan mode exited] {reason}")
                };
                self.send(&SessionUpdate::AgentMessageChunk {
                    session_id: self.session_id.clone(),
                    content: vec![text_block(&msg)],
                });
            }
            Event::CompactionDone {
                summary_chars,
                archive,
                ..
            } => {
                let msg = if *summary_chars > 0 {
                    format!(
                        "[compaction] context compacted ({} chars summary)",
                        summary_chars
                    )
                } else {
                    "[compaction] context compacted".to_string()
                };
                if let Some(ref path) = archive {
                    debug!(archive = %path, "session archived");
                }
                self.send(&SessionUpdate::AgentMessageChunk {
                    session_id: self.session_id.clone(),
                    content: vec![text_block(&msg)],
                });
            }
            Event::StreamRetrying {
                attempt, max, reason, ..
            } => {
                let msg = format!("[retry {attempt}/{max}] {reason}");
                self.send(&SessionUpdate::AgentMessageChunk {
                    session_id: self.session_id.clone(),
                    content: vec![text_block(&msg)],
                });
            }
            Event::AskRequested { questions, .. } => {
                let msg = format!("[ask] {}", questions);
                self.send(&SessionUpdate::AgentMessageChunk {
                    session_id: self.session_id.clone(),
                    content: vec![text_block(&msg)],
                });
            }
            Event::PermissionRequested { request, .. } => {
                // Send a permission request notification to the client
                let tool_call = PermissionToolCall {
                    name: request.action_type.clone(),
                    arguments: serde_json::Value::Null,
                    subject: request.path.clone(),
                    kind: Some(tool_kind_for(&request.action_type).to_string()),
                };
                self.send(&SessionUpdate::PermissionRequest {
                    session_id: self.session_id.clone(),
                    tool_call,
                    options: vec![
                        PermissionOption {
                            kind: "allow_once".to_string(),
                            label: "Allow Once".to_string(),
                            description: Some("Allow this action one time".to_string()),
                        },
                        PermissionOption {
                            kind: "deny_once".to_string(),
                            label: "Deny Once".to_string(),
                            description: Some("Deny this action one time".to_string()),
                        },
                        PermissionOption {
                            kind: "allow_session".to_string(),
                            label: "Allow for Session".to_string(),
                            description: Some("Allow this action for the session".to_string()),
                        },
                    ],
                });
            }
            _ => {
                // Other events are not mapped to ACP notifications
            }
        }
    }

    /// Send a session/update notification.
    fn send(&self, update: &SessionUpdate) {
        self.conn.notify("session/update", update);
    }

    /// Replay historical messages for a loaded session.
    pub fn replay(&self, events: &[Event]) {
        for event in events {
            match event {
                Event::StreamChunk { content, .. } => {
                    if !content.is_empty() {
                        self.send(&SessionUpdate::AgentMessageChunk {
                            session_id: self.session_id.clone(),
                            content: vec![text_block(content)],
                        });
                    }
                }
                Event::ToolCallRequested { call, .. } => {
                    let kind = tool_kind_for(&call.name);
                    let subject = extract_subject(&call.name, &call.arguments);
                    self.send(&SessionUpdate::ToolCall {
                        session_id: self.session_id.clone(),
                        tool_call_id: call.id.clone(),
                        name: call.name.clone(),
                        arguments: call.arguments.clone(),
                        kind: Some(kind.to_string()),
                        subject,
                    });
                }
                Event::ToolCallCompleted { result, .. } => {
                    let status = if result.success {
                        "completed"
                    } else {
                        "failed"
                    };
                    self.send(&SessionUpdate::ToolCallUpdate {
                        session_id: self.session_id.clone(),
                        tool_call_id: result.call_id.clone(),
                        status: status.to_string(),
                        content: Some(vec![text_block(&clip(&result.output))]),
                        truncated: result.output.len() > MAX_RESULT_CHARS,
                    });
                }
                _ => {}
            }
        }
    }
}

/// Register the `session/request_permission` RPC handler on the connection.
///
/// This handler receives the client's permission decision and forwards
/// it to the engine via the event bus.
pub async fn register_request_permission(
    conn: &Conn,
    handler: AsyncRequestHandler,
) {
    conn.handle("session/request_permission", handler).await;
}
//! Event to ACP notification mapping.
//!
//! Converts LikeCodex internal events into ACP session/update
//! notifications for the connected editor/client.

use crate::protocol::*;
use crate::server::Conn;
use likecodex_core::events::Event;
use std::sync::Arc;
use tracing::debug;

/// Maximum characters for tool result content in ACP notifications.
const MAX_RESULT_CHARS: usize = 8000;

/// Maps a tool name to its ACP tool kind.
pub fn tool_kind_for(name: &str) -> &str {
    match name {
        n if n.starts_with("read_file") || n.starts_with("list_dir") || n == "ls" || n == "glob" => {
            "read"
        }
        n if n.starts_with("grep") || n.starts_with("search") || n.starts_with("find") || n.starts_with("codegraph") || n == "code_index" => {
            "search"
        }
        n if n.starts_with("edit_file") || n.starts_with("write_file") || n.starts_with("multi_edit") || n.starts_with("move_file") || n.starts_with("delete") => {
            "edit"
        }
        n if n.starts_with("run_command") || n.starts_with("bash") || n.starts_with("git") => {
            "execute"
        }
        _ => "other",
    }
}

/// Extract a subject string from tool arguments.
pub fn extract_subject(name: &str, args: &serde_json::Value) -> Option<String> {
    if name == "run_command" {
        return args.get("command").and_then(|c| c.as_str()).map(|s| s.to_string());
    }
    for key in &["path", "file_path", "pattern"] {
        if let Some(v) = args.get(key).and_then(|a| a.as_str()) {
            return Some(v.to_string());
        }
    }
    None
}

/// Clip text to `MAX_RESULT_CHARS` (UTF-8 safe).
fn clip(text: &str) -> String {
    if text.len() <= MAX_RESULT_CHARS {
        return text.to_string();
    }
    let mut end = MAX_RESULT_CHARS;
    while end > 0 && !text.is_char_boundary(end) {
        end -= 1;
    }
    format!("{}...", &text[..end])
}

/// Build a text content block.
fn text_block(text: &str) -> ContentBlock {
    ContentBlock::Text {
        text: text.to_string(),
    }
}

/// An event sink that converts Events into ACP notifications.
pub struct UpdateSink {
    conn: Arc<Conn>,
    session_id: String,
}

impl UpdateSink {
    pub fn new(conn: Arc<Conn>, session_id: String) -> Self {
        Self { conn, session_id }
    }

    /// Emit an ACP session/update notification for the given event.
    pub fn emit(&self, event: &Event) {
        match event {
            Event::StreamChunk { content, .. } => {
                if !content.is_empty() {
                    self.send(&SessionUpdate::AgentMessageChunk {
                        session_id: self.session_id.clone(),
                        content: vec![text_block(content)],
                    });
                }
            }
            Event::ReasoningDelta { content, .. } => {
                if !content.is_empty() {
                    self.send(&SessionUpdate::AgentThoughtChunk {
                        session_id: self.session_id.clone(),
                        content: vec![text_block(content)],
                    });
                }
            }
            Event::ToolCallRequested { call, .. } => {
                let kind = tool_kind_for(&call.name);
                let subject = extract_subject(&call.name, &call.arguments);
                self.send(&SessionUpdate::ToolCall {
                    session_id: self.session_id.clone(),
                    tool_call_id: call.id.clone(),
                    name: call.name.clone(),
                    arguments: call.arguments.clone(),
                    kind: Some(kind.to_string()),
                    subject,
                });
            }
            Event::ToolCallCompleted { result, .. } => {
                let status = if result.success { "completed" } else { "failed" };
                let content = clip(&result.output);
                self.send(&SessionUpdate::ToolCallUpdate {
                    session_id: self.session_id.clone(),
                    tool_call_id: result.call_id.clone(),
                    status: status.to_string(),
                    content: Some(vec![text_block(&content)]),
                    truncated: result.output.len() > MAX_RESULT_CHARS,
                });
            }
            Event::Error { message, .. } => {
                self.send(&SessionUpdate::SessionError {
                    session_id: self.session_id.clone(),
                    message: message.clone(),
                });
            }
            Event::PlanModeChanged { active, reason, .. } => {
                let msg = if *active {
                    format!("[plan mode] {reason}")
                } else {
                    format!("[plan mode exited] {reason}")
                };
                self.send(&SessionUpdate::AgentMessageChunk {
                    session_id: self.session_id.clone(),
                    content: vec![text_block(&msg)],
                });
            }
            Event::CompactionDone {
                summary_chars, archive, ..
            } => {
                let msg = if *summary_chars > 0 {
                    format!(
                        "[compaction] context compacted ({} chars summary)",
                        summary_chars
                    )
                } else {
                    "[compaction] context compacted".to_string()
                };
                if let Some(ref path) = archive {
                    debug!(archive = %path, "session archived");
                }
                self.send(&SessionUpdate::AgentMessageChunk {
                    session_id: self.session_id.clone(),
                    content: vec![text_block(&msg)],
                });
            }
            Event::StreamRetrying { attempt, max, reason, .. } => {
                let msg = format!("[retry {attempt}/{max}] {reason}");
                self.send(&SessionUpdate::AgentMessageChunk {
                    session_id: self.session_id.clone(),
                    content: vec![text_block(&msg)],
                });
            }
            // Other events are informational and can be sent as message chunks
            Event::AskRequested { questions, .. } => {
                let msg = format!("[ask] {}", questions);
                self.send(&SessionUpdate::AgentMessageChunk {
                    session_id: self.session_id.clone(),
                    content: vec![text_block(&msg)],
                });
            }
            _ => {
                // Other events are not mapped to ACP notifications
            }
        }
    }

    /// Send a session/update notification.
    fn send(&self, update: &SessionUpdate) {
        self.conn.notify("session/update", update);
    }

    /// Replay historical messages for a loaded session.
    pub fn replay(&self, events: &[Event]) {
        for event in events {
            match event {
                Event::StreamChunk { content, .. } => {
                    if !content.is_empty() {
                        self.send(&SessionUpdate::AgentMessageChunk {
                            session_id: self.session_id.clone(),
                            content: vec![text_block(content)],
                        });
                    }
                }
                Event::ToolCallRequested { call, .. } => {
                    let kind = tool_kind_for(&call.name);
                    let subject = extract_subject(&call.name, &call.arguments);
                    self.send(&SessionUpdate::ToolCall {
                        session_id: self.session_id.clone(),
                        tool_call_id: call.id.clone(),
                        name: call.name.clone(),
                        arguments: call.arguments.clone(),
                        kind: Some(kind.to_string()),
                        subject,
                    });
                }
                Event::ToolCallCompleted { result, .. } => {
                    let status = if result.success { "completed" } else { "failed" };
                    self.send(&SessionUpdate::ToolCallUpdate {
                        session_id: self.session_id.clone(),
                        tool_call_id: result.call_id.clone(),
                        status: status.to_string(),
                        content: Some(vec![text_block(&clip(&result.output))]),
                        truncated: result.output.len() > MAX_RESULT_CHARS,
                    });
                }
                _ => {}
            }
        }
    }
}