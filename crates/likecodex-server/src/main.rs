use anyhow::{Context, Result};
use axum::{
    extract::{Path, Query, State},
    http::{header, HeaderMap, StatusCode},
    response::sse::{Event as SseEvent, Sse},
    routing::{delete, get, post},
    Json, Router,
};
use futures::StreamExt;
use likecodex_core::config::Config;
use likecodex_core::events::{Event, EventBus};
use likecodex_core::{PermissionResponse, Task};
use likecodex_indexer::{CodeGraph, FileIndex};
use likecodex_sandbox::SandboxExecutor;
use std::path::PathBuf;
use std::pin::Pin;
use std::sync::Arc;
use tokio_stream::wrappers::BroadcastStream;
use tower_http::cors::{AllowOrigin, Any, CorsLayer};
use tower_http::trace::TraceLayer;
use tracing::{info, warn};

mod engine_bridge;
mod event_mapping;

use engine_bridge::EngineBridge;
use event_mapping::{map_engine_output, map_task_status};

struct AppState {
    config: Config,
    event_bus: EventBus,
    engine_bridge: EngineBridge,
}

#[derive(serde::Deserialize)]
struct CreateTaskRequest {
    prompt: String,
    #[serde(default)]
    session_id: Option<String>,
    #[serde(default)]
    no_tools: bool,
    #[serde(default)]
    agent_mode: Option<String>,
}

#[derive(serde::Deserialize)]
struct PlanRequest {
    prompt: String,
}

#[derive(serde::Deserialize)]
struct ExecuteRequest {
    command: String,
    #[serde(default)]
    working_dir: Option<String>,
}

#[derive(serde::Deserialize)]
struct PermissionRespondRequest {
    approved: bool,
    #[serde(default)]
    grant_scope: Option<String>,
}

#[derive(serde::Deserialize)]
struct AskRespondRequest {
    answers: serde_json::Value,
}

#[derive(serde::Deserialize)]
struct RewindCheckpointRequest {
    checkpoint_id: Option<String>,
    #[serde(default)]
    mode: Option<String>,
    #[serde(default)]
    session_id: Option<String>,
}

#[derive(serde::Deserialize)]
struct IndexSearchQuery {
    pattern: String,
}

// ── New request DTOs ──────────────────────────────────────────────

#[derive(serde::Deserialize)]
struct ApproveRequest {
    request_id: String,
    approved: bool,
    #[serde(default)]
    grant_scope: Option<String>,
}

#[derive(serde::Deserialize)]
struct SessionIdRequest {
    session_id: String,
}

#[derive(serde::Deserialize)]
struct CompactRequest {
    session_id: String,
    #[serde(default)]
    focus: Option<String>,
}

#[derive(serde::Deserialize)]
struct NewSessionRequest {
    #[serde(default)]
    cwd: Option<String>,
}

#[derive(serde::Deserialize)]
struct RewindRequest {
    session_id: String,
    #[serde(default)]
    checkpoint_id: Option<String>,
    #[serde(default)]
    mode: Option<String>,
}

#[derive(serde::Deserialize)]
struct ForkRequest {
    session_id: String,
    #[serde(default)]
    label: Option<String>,
}

#[derive(serde::Deserialize)]
struct SummarizeRequest {
    session_id: String,
}

#[derive(serde::Deserialize)]
struct SetApprovalModeRequest {
    session_id: String,
    mode: String,
}

#[derive(serde::Deserialize)]
struct AnswerRequest {
    request_id: String,
    answers: serde_json::Value,
}

fn authorize_execute(headers: &HeaderMap, config: &Config) -> Result<(), (StatusCode, String)> {
    let Some(expected) = config.server.api_token.as_ref() else {
        return Ok(());
    };
    let auth = headers
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    let token = auth.strip_prefix("Bearer ").unwrap_or("");
    if token == expected {
        Ok(())
    } else {
        Err((
            StatusCode::UNAUTHORIZED,
            "invalid or missing API token".to_string(),
        ))
    }
}

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

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

    let mut config = Config::load().unwrap_or_else(|e| {
        warn!(error = %e, "failed to load config, using defaults");
        Config::default()
    });
    if config.approval.mode == "sandbox-required" {
        config.sandbox.allow_fallback = false;
    }
    if let Ok(port) = std::env::var("LIKECODEX_SERVER_PORT") {
        if let Ok(parsed) = port.parse() {
            config.server.port = parsed;
        }
    }

    let engine_url = config
        .server
        .engine_url
        .clone()
        .or_else(|| std::env::var("LIKECODEX_ENGINE_URL").ok())
        .unwrap_or_else(|| "http://127.0.0.1:9090".to_string());

    let event_bus = EventBus::new(1024);
    let engine_bridge = EngineBridge::new(engine_url);
    let state = Arc::new(AppState {
        config: config.clone(),
        event_bus,
        engine_bridge,
    });

    let cors = CorsLayer::new()
        .allow_origin(AllowOrigin::list([
            "http://localhost:3000".parse().unwrap(),
            "http://127.0.0.1:3000".parse().unwrap(),
        ]))
        .allow_methods(Any)
        .allow_headers(Any);

    let app = Router::new()
        .route("/health", get(health))
        .route("/doctor", get(get_doctor))
        .route("/config", get(get_config))
        .route("/metrics", get(get_metrics))
        .route("/tasks", post(create_task))
        .route("/chat", post(chat_stream))
        .route("/run", post(proxy_run))
        .route("/plan", post(proxy_plan))
        .route("/checkpoints", get(proxy_list_checkpoints))
        .route("/checkpoints/rewind", post(proxy_rewind_checkpoint))
        .route("/execute", post(execute_command))
        .route("/events", get(events_stream))
        .route("/permissions/pending", get(list_pending_permissions))
        .route("/permissions/:id/respond", post(respond_permission))
        .route("/ask/pending", get(proxy_list_pending_asks))
        .route("/ask/:id/respond", post(proxy_respond_ask))
        .route("/sessions", get(list_sessions))
        .route("/sessions/:id/events", get(get_session_events))
        .route("/index/search", get(index_search))
        .route("/codegraph/search", get(codegraph_search))
        // ── New ACP-compatible endpoints ──────────────────────────
        .route("/approve", post(proxy_approve))
        .route("/plan/toggle", post(proxy_toggle_plan))
        .route("/compact", post(proxy_compact))
        .route("/new", post(proxy_new_session))
        .route("/rewind", post(proxy_rewind))
        .route("/fork", post(proxy_fork))
        .route("/summarize", post(proxy_summarize))
        .route("/tool-approval-mode", post(proxy_set_approval_mode))
        .route("/answer", post(proxy_answer))
        .route("/resume", post(proxy_resume))
        .route("/sessions/:id", delete(proxy_delete_session))
        .route("/skills", get(proxy_list_skills))
        .layer(cors)
        .layer(TraceLayer::new_for_http())
        .with_state(state);

    let host = config.server.host.clone();
    let port = config.server.port;
    let listener = tokio::net::TcpListener::bind(format!("{host}:{port}")).await?;
    info!(host = %host, port = %port, "LikeCodex server listening");
    axum::serve(listener, app).await?;
    Ok(())
}

async fn health() -> &'static str {
    "ok"
}

async fn get_doctor(
    State(state): State<Arc<AppState>>,
) -> Json<serde_json::Value> {
    let engine_ok = state.engine_bridge.get("/health").await.is_ok();
    let has_key = state.config.llm.api_key.is_some()
        || std::env::var("DEEPSEEK_API_KEY").is_ok()
        || std::env::var("LIKECODEX_LLM_API_KEY").is_ok();
    Json(serde_json::json!({
        "ok": engine_ok && has_key,
        "engine_reachable": engine_ok,
        "api_key_configured": has_key,
        "approval_mode": state.config.approval.mode,
        "mcp_enabled": state.config.mcp.enabled,
        "fix": if !has_key {
            Some("Run `likecodex setup` or set DEEPSEEK_API_KEY")
        } else if !engine_ok {
            Some("Run `likecodex start` to launch the Python engine")
        } else {
            None::<&str>
        },
    }))
}

async fn get_config(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    Json(serde_json::to_value(state.config.redacted()).unwrap_or_default())
}

async fn get_metrics(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    state
        .engine_bridge
        .get("/metrics")
        .await
        .map(Json)
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))
}

async fn execute_command(
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

async fn create_task(
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

async fn chat_stream(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(req): Json<CreateTaskRequest>,
) -> Sse<Pin<Box<dyn tokio_stream::Stream<Item = Result<SseEvent, std::convert::Infallible>> + Send>>>
{
    let task = Task::new(req.prompt.clone());
    let task_id = task.id.clone();
    let _ = state.event_bus.emit(Event::TaskStarted(task)).ok();

    let bridge = state.engine_bridge.clone();
    let bus = state.event_bus.clone();

    // Extract optional API key and model from headers
    let api_key = headers
        .get("X-LikeCodex-Api-Key")
        .and_then(|v| v.to_str().ok())
        .filter(|s| !s.is_empty());
    let model = headers
        .get("X-LikeCodex-Model")
        .and_then(|v| v.to_str().ok())
        .filter(|s| !s.is_empty());

    let initial = match bridge
        .chat_stream(&req.prompt, req.session_id.as_deref(), req.no_tools, api_key, model, req.agent_mode.as_deref())
        .await
    {
        Ok(stream) => Some(stream),
        Err(e) => {
            let _ = bus.emit(Event::Error {
                task_id: Some(task_id.clone()),
                message: e.to_string(),
            });
            None
        }
    };

    let stream = futures::stream::unfold(initial, move |opt| {
        let bus = bus.clone();
        let task_id = task_id.clone();
        async move {
            match opt {
                None => None,
                Some(mut stream) => match stream.next().await {
                    None => None,
                    Some(Ok(chunk)) => {
                        for line in chunk.lines() {
                            let line = line.trim();
                            if let Some(data) = line.strip_prefix("data: ") {
                                if data != "[DONE]" {
                                    if let Ok(output) =
                                        serde_json::from_str::<serde_json::Value>(data)
                                    {
                                        let event = map_engine_output(&task_id, &output);
                                        let _ = bus.emit(event.clone()).ok();
                                        let payload =
                                            serde_json::to_string(&event).unwrap_or_default();
                                        return Some((
                                            Ok::<_, std::convert::Infallible>(
                                                SseEvent::default().data(payload),
                                            ),
                                            Some(stream),
                                        ));
                                    }
                                }
                            }
                        }
                        Some((Ok(SseEvent::default().data(chunk)), Some(stream)))
                    }
                    Some(Err(e)) => {
                        let _ = bus.emit(Event::Error {
                            task_id: Some(task_id.clone()),
                            message: e.to_string(),
                        });
                        Some((Ok(SseEvent::default().data(e.to_string())), Some(stream)))
                    }
                },
            }
        }
    })
    .boxed();

    Sse::new(stream)
}

type BoxStream =
    Pin<Box<dyn tokio_stream::Stream<Item = Result<SseEvent, std::convert::Infallible>> + Send>>;

async fn events_stream(State(state): State<Arc<AppState>>) -> Sse<BoxStream> {
    let receiver = state.event_bus.subscribe();
    let stream = BroadcastStream::new(receiver)
        .filter(|event| futures::future::ready(event.is_ok()))
        .map(|event| {
            let e = event.unwrap();
            Ok::<_, std::convert::Infallible>(
                SseEvent::default().data(serde_json::to_string(&e).unwrap_or_default()),
            )
        })
        .boxed();
    Sse::new(stream)
}

async fn list_pending_permissions(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .get("/permissions/pending")
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

async fn respond_permission(
    State(state): State<Arc<AppState>>,
    axum::extract::Path(id): axum::extract::Path<String>,
    Json(req): Json<PermissionRespondRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .post(
            &format!("/permissions/{id}/respond"),
            &serde_json::json!({
                "approved": req.approved,
                "grant_scope": req.grant_scope.unwrap_or_else(|| "once".to_string()),
            }),
        )
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;

    let response = if req.approved {
        PermissionResponse::AllowOnce
    } else {
        PermissionResponse::DenyOnce
    };
    let _ = state
        .event_bus
        .emit(Event::PermissionResponded {
            task_id: String::new(),
            request_id: id,
            response,
        })
        .ok();

    Ok(Json(body))
}

async fn list_sessions(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .get("/sessions")
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

async fn get_session_events(
    State(state): State<Arc<AppState>>,
    axum::extract::Path(id): axum::extract::Path<String>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .get(&format!("/sessions/{id}/events"))
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

async fn index_search(Query(query): Query<IndexSearchQuery>) -> Json<serde_json::Value> {
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let mut index = FileIndex::new();
    let results = match index.index(&cwd) {
        Ok(()) => index
            .search_by_name(&query.pattern)
            .into_iter()
            .take(50)
            .map(|entry| {
                serde_json::json!({
                    "path": entry.path.display().to_string(),
                    "language": entry.language,
                    "size": entry.size,
                })
            })
            .collect::<Vec<_>>(),
        Err(e) => {
            return Json(serde_json::json!({ "error": e.to_string(), "results": [] }));
        }
    };
    Json(serde_json::json!({ "pattern": query.pattern, "results": results }))
}

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

async fn codegraph_search(
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

    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let mut graph = CodeGraph::new();
    if let Err(e) = graph.build(&cwd) {
        return Json(serde_json::json!({ "error": e.to_string(), "results": [] }));
    }
    let _ = graph.save_cached(&cwd);
    let results = graph
        .search(&query.pattern)
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
    Json(serde_json::json!({
        "pattern": query.pattern,
        "results": results,
        "files": graph.file_count,
    }))
}

async fn proxy_run(
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

async fn proxy_plan(
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

async fn proxy_list_checkpoints(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .get("/checkpoints")
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

async fn proxy_rewind_checkpoint(
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

async fn proxy_list_pending_asks(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .get("/ask/pending")
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

async fn proxy_respond_ask(
    State(state): State<Arc<AppState>>,
    axum::extract::Path(id): axum::extract::Path<String>,
    Json(req): Json<AskRespondRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .post(
            &format!("/ask/{id}/respond"),
            &serde_json::json!({ "answers": req.answers }),
        )
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

// ── New ACP-compatible handler functions ──────────────────────────

/// POST /approve — approve a pending tool call permission request.
async fn proxy_approve(
    State(state): State<Arc<AppState>>,
    Json(req): Json<ApproveRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .post(
            &format!("/permissions/{}/respond", req.request_id),
            &serde_json::json!({
                "approved": req.approved,
                "grant_scope": req.grant_scope.unwrap_or_else(|| "once".to_string()),
            }),
        )
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;

    let response = if req.approved {
        PermissionResponse::AllowOnce
    } else {
        PermissionResponse::DenyOnce
    };
    let _ = state
        .event_bus
        .emit(Event::PermissionResponded {
            task_id: String::new(),
            request_id: req.request_id,
            response,
        })
        .ok();

    Ok(Json(body))
}

/// POST /plan/toggle — toggle plan mode for a session.
async fn proxy_toggle_plan(
    State(state): State<Arc<AppState>>,
    Json(req): Json<SessionIdRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .post(
            "/plan/toggle",
            &serde_json::json!({ "session_id": req.session_id }),
        )
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

/// POST /compact — trigger context compaction for a session.
async fn proxy_compact(
    State(state): State<Arc<AppState>>,
    Json(req): Json<CompactRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .post(
            "/compact",
            &serde_json::json!({
                "session_id": req.session_id,
                "focus": req.focus,
            }),
        )
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

/// POST /new — create a new session.
async fn proxy_new_session(
    State(state): State<Arc<AppState>>,
    Json(req): Json<NewSessionRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .post(
            "/new",
            &serde_json::json!({ "cwd": req.cwd }),
        )
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

/// POST /rewind — rewind a session to a checkpoint.
async fn proxy_rewind(
    State(state): State<Arc<AppState>>,
    Json(req): Json<RewindRequest>,
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

/// POST /fork — fork a session at a checkpoint.
async fn proxy_fork(
    State(state): State<Arc<AppState>>,
    Json(req): Json<ForkRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .post(
            "/fork",
            &serde_json::json!({
                "session_id": req.session_id,
                "label": req.label,
            }),
        )
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

/// POST /summarize — generate a summary of a session.
async fn proxy_summarize(
    State(state): State<Arc<AppState>>,
    Json(req): Json<SummarizeRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .post(
            "/summarize",
            &serde_json::json!({ "session_id": req.session_id }),
        )
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

/// POST /tool-approval-mode — set the tool approval mode.
async fn proxy_set_approval_mode(
    State(state): State<Arc<AppState>>,
    Json(req): Json<SetApprovalModeRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .post(
            "/tool-approval-mode",
            &serde_json::json!({
                "session_id": req.session_id,
                "mode": req.mode,
            }),
        )
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

/// POST /answer — answer an ask request from the agent.
async fn proxy_answer(
    State(state): State<Arc<AppState>>,
    Json(req): Json<AnswerRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .post(
            &format!("/ask/{}/respond", req.request_id),
            &serde_json::json!({ "answers": req.answers }),
        )
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;

    let _ = state
        .event_bus
        .emit(Event::AskResponded {
            task_id: String::new(),
            request_id: req.request_id,
            answers: req.answers,
        })
        .ok();

    Ok(Json(body))
}

/// POST /resume — resume a saved session.
async fn proxy_resume(
    State(state): State<Arc<AppState>>,
    Json(req): Json<SessionIdRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .post(
            "/resume",
            &serde_json::json!({ "session_id": req.session_id }),
        )
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

/// DELETE /sessions/:id — delete a session.
async fn proxy_delete_session(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .post(
            "/sessions/delete",
            &serde_json::json!({ "session_id": id }),
        )
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

/// GET /skills — list available skills.
async fn proxy_list_skills(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .get("/skills")
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}
