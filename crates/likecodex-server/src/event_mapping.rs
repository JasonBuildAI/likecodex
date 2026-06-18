use likecodex_core::{
    Message, PermissionRequest, Plan, PlanStep, Role, StepStatus, Task, ToolCall, ToolResult,
};
use likecodex_core::events::Event;
use serde_json::Value;

/// Map a Python engine output object to a structured LikeCodex event.
pub fn map_engine_output(task_id: &str, output: &Value) -> Event {
    let event_type = output["type"].as_str().unwrap_or("assistant");
    let content = output["content"].as_str().unwrap_or("").to_string();

    match event_type {
        "assistant" => Event::StreamChunk {
            task_id: task_id.to_string(),
            content,
        },
        "tool_call" => {
            let tool_calls = output["tool_calls"].as_array().cloned().unwrap_or_default();
            if let Some(tc) = tool_calls.first() {
                Event::ToolCallRequested {
                    task_id: task_id.to_string(),
                    call: ToolCall {
                        id: tc["id"].as_str().unwrap_or("").to_string(),
                        name: tc["name"].as_str().unwrap_or("").to_string(),
                        arguments: tc["arguments"].clone(),
                    },
                }
            } else {
                Event::StreamChunk {
                    task_id: task_id.to_string(),
                    content,
                }
            }
        }
        "tool_result" => Event::ToolCallCompleted {
            task_id: task_id.to_string(),
            result: ToolResult {
                call_id: output["call_id"]
                    .as_str()
                    .unwrap_or("")
                    .to_string(),
                success: !content.contains("\"error\""),
                output: content,
                metadata: Default::default(),
            },
        },
        "plan" => Event::PlanUpdated(Plan {
            task_id: task_id.to_string(),
            reasoning: content.clone(),
            steps: vec![PlanStep {
                id: "step".to_string(),
                description: content,
                status: StepStatus::InProgress,
                depends_on: vec![],
            }],
        }),
        "permission" => Event::PermissionRequested {
            task_id: task_id.to_string(),
            request: PermissionRequest {
                id: output["request_id"]
                    .as_str()
                    .unwrap_or("")
                    .to_string(),
                action_type: output["action_type"]
                    .as_str()
                    .unwrap_or("tool")
                    .to_string(),
                description: content,
                command: output["command"].as_str().map(|s| s.to_string()),
                path: output["path"].as_str().map(|s| s.to_string()),
            },
        },
        "subagent" => Event::StreamChunk {
            task_id: task_id.to_string(),
            content: format!("[subagent] {content}"),
        },
        "error" => Event::Error {
            task_id: Some(task_id.to_string()),
            message: content,
        },
        _ => Event::StreamChunk {
            task_id: task_id.to_string(),
            content: format!("[{event_type}] {content}"),
        },
    }
}

pub fn map_task_status(task_id: &str, prompt: &str, status: &str) -> Event {
    let mut task = Task::new(prompt);
    task.id = task_id.to_string();
    task.status = match status {
        "failed" => likecodex_core::TaskStatus::Failed,
        "running" => likecodex_core::TaskStatus::Running,
        _ => likecodex_core::TaskStatus::Completed,
    };
    Event::TaskCompleted(task)
}

pub fn assistant_message_event(task_id: &str, content: &str) -> Event {
    Event::MessageAdded {
        task_id: task_id.to_string(),
        message: Message {
            role: Role::Assistant,
            content: content.to_string(),
            tool_calls: None,
            tool_call_id: None,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn maps_stream_chunk() {
        let event = map_engine_output(
            "t1",
            &json!({"type": "assistant", "content": "hello"}),
        );
        match event {
            Event::StreamChunk { content, .. } => assert_eq!(content, "hello"),
            _ => panic!("expected stream chunk"),
        }
    }

    #[test]
    fn maps_error() {
        let event = map_engine_output(
            "t1",
            &json!({"type": "error", "content": "boom"}),
        );
        match event {
            Event::Error { message, .. } => assert_eq!(message, "boom"),
            _ => panic!("expected error"),
        }
    }
}
