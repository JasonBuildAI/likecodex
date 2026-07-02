use axum::{
    extract::{Query, State},
    http::{HeaderMap, StatusCode},
    response::Json,
};
use futures::StreamExt;
use likecodex_core::events::Event;
use likecodex_core::Task;
use likecodex_indexer::{CodeGraph, FileIndex};
use likecodex_sandbox::SandboxExecutor;
use std::path::PathBuf;
use std::sync::Arc;

use crate::dto::{
    CreateTaskRequest, ExecuteRequest, IndexSearchQuery, PlanRequest, RewindCheckpointRequest,
};
use crate::event_mapping::{map_engine_output, map_task_status};
use crate::middleware::auth::authorize_execute;
use crate::state::AppState;

/// POST /tasks — create a new task and start processing it asynchronously.
pub async fn create_task(
    State(state): State<Arc<AppState>>,
    Json(req): Json<CreateTaskRequest>,
) -> Json<serde_json::Value> {
    let task = Task::new(req.prompt.clone());
    let task_id = task.id.clone();
    let _ = state.event_bus.emit(Event::TaskStarted(task.clone())).ok();

    let bridge = state.engine_bridge.clone();
    let bus = state.event_bus.clone();
    let prompt = req.prompt.clone();

    tokio::spawn(async move {
        match bridge.create_task(&prompt).await {
            Ok(engine_task_id) => {
                match bridge.poll_task_outputs(engine_task_id.clone()).await {
                    Ok(mut stream) => {
                        while let Some(result) = stream.next().await {
                            match result {
                                Ok(output) => {
                                    let event = map_engine_output(&task_id, &output);
                                    let _ = bus.emit(event).ok();
                                }
                                Err(e) => {
                                    let _ = bus.emit(Event::Error {
                                        task_id: Some(task_id.clone()),
                                        message: e.to_string(),
                                    });
                                }
                            }
                        }
                    }
                    Err(e) => {
                        let _ = bus.emit(Event::Error {
                            task_id: Some(task_id.clone()),
                            message: e.to_string(),
                        });
                    }
                }

                let final_status = bridge
                    .get_task(&engine_task_id)
                    .await
                    .ok()
                    .and_then(|body| body["status"].as_str().map(|s| s.to_string()))
                    .unwrap_or_else(|| "completed".to_string());

                let _ = bus
                    .emit(map_task_status(&task_id, &prompt, &final_status))
                    .ok();
                let _ = bus.emit(Event::StreamFinished {
                    task_id: task_id.clone(),
                });
            }
            Err(e) => {
                let _ = bus.emit(Event::Error {
                    task_id: Some(task_id.clone()),
                    message: e.to_string(),
                });
                let _ = bus.emit(map_task_status(&task_id, &prompt, "failed")).ok();
            }
        }
    });

    Json(serde_json::json!({ "task": task }))
}

/// POST /run — proxy a run command to the engine.
pub async fn proxy_run(
    State(state): State<Arc<AppState>>,
    Json(req): Json<CreateTaskRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .post(
            "/run",
            &serde_json::json!({
                "prompt": req.prompt,
                "session_id": req.session_id,
            }),
        )
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

/// POST /plan — proxy a plan request to the engine.
pub async fn proxy_plan(
    State(state): State<Arc<AppState>>,
    Json(req): Json<PlanRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .post("/plan", &serde_json::json!({ "prompt": req.prompt }))
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

/// GET /checkpoints — list available checkpoints.
pub async fn proxy_list_checkpoints(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .get("/checkpoints")
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

/// POST /checkpoints/rewind — rewind to a specific checkpoint.
pub async fn proxy_rewind_checkpoint(
    State(state): State<Arc<AppState>>,
    Json(req): Json<RewindCheckpointRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .post(
            "/checkpoints/rewind",
            &serde_json::json!({
                "checkpoint_id": req.checkpoint_id,
                "mode": req.mode.unwrap_or_else(|| "code".to_string()),
                "session_id": req.session_id,
            }),
        )
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

/// GET /execute — execute a command in the sandbox and return the result.
pub async fn execute_command(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(req): Json<ExecuteRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<serde_json::Value>)> {
    authorize_execute(&headers, &state.config)
        .map_err(|(code, msg)| (code, Json(serde_json::json!({ "error": msg }))))?;

    let working_dir = resolve_working_dir(req.working_dir)
        .map_err(|(code, msg)| (code, Json(serde_json::json!({ "error": msg }))))?;

    let mut sandbox_config = state.config.sandbox.clone();
    if state.config.approval.mode == "sandbox-required" {
        sandbox_config.allow_fallback = false;
    }
    let executor = SandboxExecutor::new(sandbox_config);
    match executor.execute(&req.command, &working_dir).await {
        Ok(result) => Ok(Json(serde_json::json!({
            "command": result.command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "duration_ms": result.duration_ms,
        }))),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({ "error": e.to_string() })),
        )),
    }
}

/// GET /index/search — search the file index by pattern.
pub async fn index_search(Query(query): Query<IndexSearchQuery>) -> Json<serde_json::Value> {
    let cwd = tokio::task::spawn_blocking(|| {
        std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
    })
    .await
    .unwrap_or_else(|_| PathBuf::from("."));

    let pattern = query.pattern.clone();
    let result = tokio::task::spawn_blocking(move || -> Vec<serde_json::Value> {
        let mut index = FileIndex::new();
        if index.index_or_load(&cwd).is_err() {
            return vec![];
        }
        index
            .search_by_name(&pattern)
            .into_iter()
            .take(50)
            .map(|entry| {
                serde_json::json!({
                    "path": entry.path.display().to_string(),
                    "language": entry.language,
                    "size": entry.size,
                })
            })
            .collect::<Vec<_>>()
    })
    .await
    .unwrap_or_default();

    Json(serde_json::json!({ "pattern": query.pattern, "results": result }))
}

/// GET /codegraph/search — search the code graph by symbol pattern.
pub async fn codegraph_search(
    State(state): State<Arc<AppState>>,
    Query(query): Query<IndexSearchQuery>,
) -> Json<serde_json::Value> {
    let path = format!(
        "/codegraph/search?pattern={}",
        percent_encode_query(&query.pattern)
    );
    if let Ok(body) = state.engine_bridge.get(&path).await {
        return Json(body);
    }

    let cwd = tokio::task::spawn_blocking(|| {
        std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
    })
    .await
    .unwrap_or_else(|_| PathBuf::from("."));

    let pattern = query.pattern.clone();
    let result = tokio::task::spawn_blocking(move || {
        let mut graph = CodeGraph::new();
        if let Err(e) = graph.build(&cwd) {
            return serde_json::json!({ "error": e.to_string(), "results": [] });
        }
        let _ = graph.save_cached(&cwd);
        let results = graph
            .search(&pattern)
            .into_iter()
            .take(50)
            .map(|sym| {
                serde_json::json!({
                    "name": sym.name,
                    "kind": sym.kind,
                    "path": sym.path.display().to_string(),
                    "line": sym.line,
                })
            })
            .collect::<Vec<_>>();
        serde_json::json!({
            "pattern": pattern,
            "results": results,
            "files": graph.file_count,
        })
    })
    .await
    .unwrap_or_else(|_| serde_json::json!({ "error": "task panicked", "results": [] }));

    Json(result)
}

/// Percent-encode a query string for safe use in URL query parameters.
fn percent_encode_query(value: &str) -> String {
    value
        .bytes()
        .map(|b| match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                (b as char).to_string()
            }
            _ => format!("%{b:02X}"),
        })
        .collect()
}

/// Resolve and validate a working directory path, ensuring it stays within the server cwd.
fn resolve_working_dir(requested: Option<String>) -> Result<PathBuf, (StatusCode, String)> {
    let cwd =
        std::env::current_dir().map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let dir = requested.map(PathBuf::from).unwrap_or_else(|| cwd.clone());
    let canonical = dir.canonicalize().map_err(|_| {
        (
            StatusCode::BAD_REQUEST,
            "invalid working directory".to_string(),
        )
    })?;
    let cwd_canonical = cwd.canonicalize().map_err(|_| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            "failed to resolve server working directory".to_string(),
        )
    })?;
    if !canonical.starts_with(&cwd_canonical) {
        return Err((
            StatusCode::FORBIDDEN,
            "working directory must stay within server cwd".to_string(),
        ));
    }
    Ok(canonical)
}
