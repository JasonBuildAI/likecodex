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
        "delta" => Event::StreamChunk {
            task_id: task_id.to_string(),
            content,
        },
        "retrying" => {
            let attempt = output
                .get("metadata")
                .and_then(|v| v.get("retry_attempt"))
                .and_then(|v| v.as_i64())
                .unwrap_or(1) as i32;
            let max = output
                .get("metadata")
                .and_then(|v| v.get("retry_max"))
                .and_then(|v| v.as_i64())
                .unwrap_or(1) as i32;
            let reason = output
                .get("metadata")
                .and_then(|v| v.get("reason"))
                .and_then(|v| v.as_str())
                .unwrap_or("retry")
                .to_string();
            Event::StreamRetrying {
                task_id: task_id.to_string(),
                attempt,
                max,
                message: content,
                reason,
            }
        }
        "tool_dispatch" => {
            let meta = output.get("metadata");
            let tool_name = meta
                .and_then(|v| v.get("tool_name"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let call_id = meta
                .and_then(|v| v.get("tool_call_id"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let partial = meta
                .and_then(|v| v.get("partial"))
                .and_then(|v| v.as_bool())
                .unwrap_or(true);
            let arguments = if partial {
                serde_json::json!({"partial": true})
            } else {
                meta.and_then(|v| v.get("arguments"))
                    .cloned()
                    .unwrap_or_else(|| serde_json::json!({}))
            };
            Event::ToolCallRequested {
                task_id: task_id.to_string(),
                call: ToolCall {
                    id: call_id,
                    name: tool_name,
                    arguments,
                },
            }
        }
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
        "tool_result" => {
            let call_id = output
                .get("metadata")
                .and_then(|v| v.get("tool_call_id"))
                .and_then(|v| v.as_str())
                .or_else(|| output["call_id"].as_str())
                .unwrap_or("")
                .to_string();
            Event::ToolCallCompleted {
                task_id: task_id.to_string(),
                result: ToolResult {
                    call_id,
                    success: !content.contains("\"error\""),
                    output: content,
                    metadata: Default::default(),
                },
            }
        }
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
        "permission" => {
            let parsed = serde_json::from_str::<Value>(&content).unwrap_or(Value::Null);
            let request_id = parsed
                .get("request_id")
                .and_then(|v| v.as_str())
                .or_else(|| output["request_id"].as_str())
                .unwrap_or("")
                .to_string();
            let tool = parsed
                .get("tool")
                .and_then(|v| v.as_str())
                .or_else(|| output["action_type"].as_str())
                .unwrap_or("tool")
                .to_string();
            let args = parsed.get("arguments");
            Event::PermissionRequested {
                task_id: task_id.to_string(),
                request: PermissionRequest {
                    id: request_id,
                    action_type: tool,
                    description: content,
                    command: args
                        .and_then(|v| v.get("command"))
                        .and_then(|v| v.as_str())
                        .or_else(|| output["command"].as_str())
                        .map(str::to_string),
                    path: args
                        .and_then(|v| v.get("path"))
                        .and_then(|v| v.as_str())
                        .or_else(|| output["path"].as_str())
                        .map(str::to_string),
                },
            }
        }
        "permission_responded" => {
            let parsed = serde_json::from_str::<Value>(&content).unwrap_or(Value::Null);
            let request_id = parsed
                .get("request_id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let approved = parsed
                .get("approved")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            let response = if approved {
                likecodex_core::PermissionResponse::AllowOnce
            } else {
                likecodex_core::PermissionResponse::DenyOnce
            };
            Event::PermissionResponded {
                task_id: task_id.to_string(),
                request_id,
                response,
            }
        }
        "notice" => Event::StreamChunk {
            task_id: task_id.to_string(),
            content: format!("[notice] {content}"),
        },
        "usage" => Event::StreamChunk {
            task_id: task_id.to_string(),
            content: format!("[usage]{content}"),
        },
        "subagent" => Event::StreamChunk {
            task_id: task_id.to_string(),
            content: format!("[subagent] {content}"),
        },
        "compaction_started" => {
            let trigger = serde_json::from_str::<Value>(&content)
                .ok()
                .and_then(|v| v.get("trigger").and_then(|t| t.as_str()).map(str::to_string))
                .unwrap_or_else(|| "auto".to_string());
            Event::CompactionStarted {
                task_id: task_id.to_string(),
                trigger,
            }
        }
        "compaction" if content.contains("\"trigger\"") || content.contains("\"phase\"") => {
            let trigger = serde_json::from_str::<Value>(&content)
                .ok()
                .and_then(|v| v.get("trigger").and_then(|t| t.as_str()).map(str::to_string))
                .unwrap_or_else(|| "auto".to_string());
            Event::CompactionStarted {
                task_id: task_id.to_string(),
                trigger,
            }
        }
        "compaction_done" | "compaction" => {
            let parsed = serde_json::from_str::<Value>(&content).unwrap_or(Value::Null);
            Event::CompactionDone {
                task_id: task_id.to_string(),
                messages: parsed
                    .get("pruned_results")
                    .and_then(|v| v.as_i64())
                    .unwrap_or(0) as i32,
                summary_chars: parsed
                    .get("pruned_chars")
                    .and_then(|v| v.as_i64())
                    .unwrap_or(0) as i32,
                archive: parsed
                    .get("archive")
                    .and_then(|v| v.as_str())
                    .map(str::to_string),
            }
        }
        "checkpoint" => {
            let parsed = serde_json::from_str::<Value>(&content).unwrap_or(Value::Null);
            let files = parsed
                .get("files")
                .and_then(|v| v.as_array())
                .map(|arr| {
                    arr.iter()
                        .filter_map(|v| v.as_str().map(str::to_string))
                        .collect()
                })
                .unwrap_or_default();
            Event::CheckpointCreated {
                task_id: task_id.to_string(),
                checkpoint_id: parsed
                    .get("checkpoint_id")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
                label: parsed
                    .get("label")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
                files,
            }
        }
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
    fn maps_delta_chunk() {
        let event = map_engine_output(
            "t1",
            &json!({"type": "delta", "content": "partial"}),
        );
        match event {
            Event::StreamChunk { content, .. } => assert_eq!(content, "partial"),
            _ => panic!("expected stream chunk"),
        }
    }

    #[test]
    fn maps_compaction_events() {
        let started = map_engine_output(
            "t1",
            &json!({"type": "compaction_started", "content": "{\"trigger\":\"auto\"}"}),
        );
        match started {
            Event::CompactionStarted { trigger, .. } => assert_eq!(trigger, "auto"),
            _ => panic!("expected compaction started"),
        }
        let done = map_engine_output(
            "t1",
            &json!({"type": "compaction_done", "content": "{\"compacted\":true,\"archive\":\"/tmp/x\"}"}),
        );
        match done {
            Event::CompactionDone { archive, .. } => assert_eq!(archive.as_deref(), Some("/tmp/x")),
            _ => panic!("expected compaction done"),
        }
    }

    #[test]
    fn maps_stream_retrying() {
        let event = map_engine_output(
            "t1",
            &json!({
                "type": "retrying",
                "content": "recover please",
                "metadata": {"retry_attempt": 1, "retry_max": 1, "reason": "stream_recovery"}
            }),
        );
        match event {
            Event::StreamRetrying {
                attempt,
                max,
                message,
                reason,
                ..
            } => {
                assert_eq!(attempt, 1);
                assert_eq!(max, 1);
                assert_eq!(message, "recover please");
                assert_eq!(reason, "stream_recovery");
            }
            _ => panic!("expected stream retrying"),
        }
    }

    #[test]
    fn maps_tool_dispatch() {
        let event = map_engine_output(
            "t1",
            &json!({"type": "tool_dispatch", "content": "", "metadata": {"tool_name": "bash"}}),
        );
        match event {
            Event::ToolCallRequested { call, .. } => {
                assert_eq!(call.name, "bash");
            }
            _ => panic!("expected tool dispatch"),
        }
    }

    #[test]
    fn maps_full_tool_dispatch() {
        let event = map_engine_output(
            "t1",
            &json!({
                "type": "tool_dispatch",
                "content": "",
                "metadata": {
                    "tool_name": "read_file",
                    "tool_call_id": "c1",
                    "partial": false,
                    "arguments": {"path": "a.txt"}
                }
            }),
        );
        match event {
            Event::ToolCallRequested { call, .. } => {
                assert_eq!(call.id, "c1");
                assert_eq!(call.name, "read_file");
                assert_eq!(call.arguments["path"], "a.txt");
            }
            _ => panic!("expected tool dispatch"),
        }
    }

    #[test]
    fn maps_permission_from_content_json() {
        let event = map_engine_output(
            "t1",
            &json!({
                "type": "permission",
                "content": "{\"request_id\":\"req-1\",\"tool\":\"write_file\",\"arguments\":{\"path\":\"a.txt\"},\"reason\":\"policy requires approval\"}"
            }),
        );
        match event {
            Event::PermissionRequested { request, .. } => {
                assert_eq!(request.id, "req-1");
                assert_eq!(request.action_type, "write_file");
                assert_eq!(request.path.as_deref(), Some("a.txt"));
            }
            _ => panic!("expected permission requested"),
        }
    }

    #[test]
    fn maps_permission_responded() {
        let event = map_engine_output(
            "t1",
            &json!({
                "type": "permission_responded",
                "content": "{\"request_id\":\"req-1\",\"approved\":true}"
            }),
        );
        match event {
            Event::PermissionResponded {
                request_id,
                response,
                ..
            } => {
                assert_eq!(request_id, "req-1");
                assert_eq!(response, likecodex_core::PermissionResponse::AllowOnce);
            }
            _ => panic!("expected permission responded"),
        }
    }

    #[test]
    fn maps_usage_event() {
        let event = map_engine_output(
            "t1",
            &json!({"type": "usage", "content": "  · 120 tok · in 100 (80 cached / 20 new) · out 20"}),
        );
        match event {
            Event::StreamChunk { content, .. } => {
                assert!(content.starts_with("[usage]"));
                assert!(content.contains("120 tok"));
            }
            _ => panic!("expected usage stream chunk"),
        }
    }

    #[test]
    fn maps_tool_result_call_id_from_metadata() {
        let event = map_engine_output(
            "t1",
            &json!({
                "type": "tool_result",
                "content": "{\"ok\":true}",
                "metadata": {"tool_call_id": "call-9"}
            }),
        );
        match event {
            Event::ToolCallCompleted { result, .. } => assert_eq!(result.call_id, "call-9"),
            _ => panic!("expected tool result"),
        }
    }

    #[test]
    fn maps_checkpoint_created() {
        let event = map_engine_output(
            "t1",
            &json!({
                "type": "checkpoint",
                "content": "{\"checkpoint_id\":\"cp1\",\"label\":\"write_file\",\"files\":[\"a.txt\"]}"
            }),
        );
        match event {
            Event::CheckpointCreated {
                checkpoint_id,
                label,
                files,
                ..
            } => {
                assert_eq!(checkpoint_id, "cp1");
                assert_eq!(label, "write_file");
                assert_eq!(files, vec!["a.txt".to_string()]);
            }
            _ => panic!("expected checkpoint created"),
        }
    }
}
