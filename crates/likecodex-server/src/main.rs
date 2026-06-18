use anyhow::{Context, Result};
use axum::{
    extract::{Query, State},
    http::{header, HeaderMap, StatusCode},
    response::sse::{Event as SseEvent, Sse},
    routing::{get, post},
    Json, Router,
};
use futures::StreamExt;
use likecodex_core::config::Config;
use likecodex_core::events::{Event, EventBus};
use likecodex_core::Task;
use likecodex_indexer::FileIndex;
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
}

#[derive(serde::Deserialize)]
struct IndexSearchQuery {
    pattern: String,
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
        Err((StatusCode::UNAUTHORIZED, "invalid or missing API token".to_string()))
    }
}

fn resolve_working_dir(requested: Option<String>) -> Result<PathBuf, (StatusCode, String)> {
    let cwd = std::env::current_dir()
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let dir = requested
        .map(PathBuf::from)
        .unwrap_or_else(|| cwd.clone());
    let canonical = dir
        .canonicalize()
        .map_err(|_| (StatusCode::BAD_REQUEST, "invalid working directory".to_string()))?;
    let cwd_canonical = cwd
        .canonicalize()
        .unwrap_or(cwd);
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
        .route("/config", get(get_config))
        .route("/metrics", get(get_metrics))
        .route("/tasks", post(create_task))
        .route("/chat", post(chat_stream))
        .route("/execute", post(execute_command))
        .route("/events", get(events_stream))
        .route("/permissions/pending", get(list_pending_permissions))
        .route("/permissions/:id/respond", post(respond_permission))
        .route("/sessions", get(list_sessions))
        .route("/sessions/:id/events", get(get_session_events))
        .route("/index/search", get(index_search))
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

async fn get_config(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    Json(serde_json::to_value(state.config.redacted()).unwrap_or_default())
}

async fn get_metrics(State(state): State<Arc<AppState>>) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
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
    authorize_execute(&headers, &state.config).map_err(|(code, msg)| {
        (
            code,
            Json(serde_json::json!({ "error": msg })),
        )
    })?;

    let working_dir = resolve_working_dir(req.working_dir).map_err(|(code, msg)| {
        (
            code,
            Json(serde_json::json!({ "error": msg })),
        )
    })?;

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

                let _ = bus.emit(map_task_status(&task_id, &prompt, &final_status)).ok();
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
    Json(req): Json<CreateTaskRequest>,
) -> Sse<Pin<Box<dyn tokio_stream::Stream<Item = Result<SseEvent, std::convert::Infallible>> + Send>>>
{
    let task = Task::new(req.prompt.clone());
    let task_id = task.id.clone();
    let _ = state.event_bus.emit(Event::TaskStarted(task)).ok();

    let bridge = state.engine_bridge.clone();
    let bus = state.event_bus.clone();

    let initial = match bridge.chat_stream(&req.prompt).await {
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
                                    if let Ok(output) = serde_json::from_str::<serde_json::Value>(data)
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
                        Some((
                            Ok(SseEvent::default().data(chunk)),
                            Some(stream),
                        ))
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
            &serde_json::json!({ "approved": req.approved }),
        )
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
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

async fn index_search(
    Query(query): Query<IndexSearchQuery>,
) -> Json<serde_json::Value> {
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
