pub mod chat;
pub mod health;
pub mod permissions;
pub mod sessions;
pub mod tasks;
pub mod terminal;

use axum::{
    routing::{delete, get, post},
    Router,
};
use std::sync::Arc;
use tower_http::cors::{AllowOrigin, Any, CorsLayer};

use crate::middleware::request_log::apply_request_logging;
use crate::state::AppState;

/// Build and return the full Axum router with all routes configured.
pub fn configure_routes(state: Arc<AppState>) -> Router {
    let cors = CorsLayer::new()
        .allow_origin(AllowOrigin::list([
            "http://localhost:3000".parse().unwrap(),
            "http://127.0.0.1:3000".parse().unwrap(),
        ]))
        .allow_methods(Any)
        .allow_headers(Any);

    let router = Router::new()
        // Health / diagnostics
        .route("/health", get(health::health))
        .route("/doctor", get(health::get_doctor))
        .route("/config", get(health::get_config))
        .route("/metrics", get(health::get_metrics))
        // Tasks
        .route("/tasks", post(tasks::create_task))
        .route("/run", post(tasks::proxy_run))
        .route("/plan", post(tasks::proxy_plan))
        .route("/checkpoints", get(tasks::proxy_list_checkpoints))
        .route("/checkpoints/rewind", post(tasks::proxy_rewind_checkpoint))
        .route("/execute", post(tasks::execute_command))
        .route("/index/search", get(tasks::index_search))
        .route("/codegraph/search", get(tasks::codegraph_search))
        // Chat / SSE
        .route("/chat", post(chat::chat_stream))
        .route("/events", get(chat::events_stream))
        // Permissions
        .route("/permissions/pending", get(permissions::list_pending_permissions))
        .route("/permissions/:id/respond", post(permissions::respond_permission))
        .route("/ask/pending", get(permissions::proxy_list_pending_asks))
        .route("/ask/:id/respond", post(permissions::proxy_respond_ask))
        .route("/approve", post(permissions::proxy_approve))
        .route("/answer", post(permissions::proxy_answer))
        // Sessions
        .route("/sessions", get(sessions::list_sessions))
        .route("/sessions/:id/events", get(sessions::get_session_events))
        .route("/plan/toggle", post(sessions::proxy_toggle_plan))
        .route("/compact", post(sessions::proxy_compact))
        .route("/new", post(sessions::proxy_new_session))
        .route("/rewind", post(sessions::proxy_rewind))
        .route("/fork", post(sessions::proxy_fork))
        .route("/summarize", post(sessions::proxy_summarize))
        .route("/tool-approval-mode", post(sessions::proxy_set_approval_mode))
        .route("/resume", post(sessions::proxy_resume))
        .route("/sessions/:id", delete(sessions::proxy_delete_session))
        .route("/skills", get(sessions::proxy_list_skills))
        // Terminal
        .route("/api/terminal/create", post(terminal::pty_create))
        .route("/api/terminal/:id/close", post(terminal::pty_close))
        .route("/api/terminal/list", get(terminal::pty_list))
        .route("/api/terminal/:id/resize", post(terminal::pty_resize))
        .route("/api/terminal/:id/ws", get(terminal::pty_ws_handler))
        .layer(cors)
        .with_state(state);

    apply_request_logging(router)
}
