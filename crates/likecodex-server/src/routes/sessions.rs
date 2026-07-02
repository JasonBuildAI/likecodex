use axum::{extract::State, http::StatusCode, response::Json};
use std::sync::Arc;

use crate::dto::{
    CompactRequest, ForkRequest, NewSessionRequest, RewindRequest, SessionIdRequest,
    SetApprovalModeRequest, SummarizeRequest,
};
use crate::state::AppState;

/// GET /sessions — list all active sessions.
pub async fn list_sessions(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .get("/sessions")
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

/// GET /sessions/:id/events — get events for a specific session.
pub async fn get_session_events(
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

/// POST /plan/toggle — toggle plan mode for a session.
pub async fn proxy_toggle_plan(
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
pub async fn proxy_compact(
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
pub async fn proxy_new_session(
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
pub async fn proxy_rewind(
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
pub async fn proxy_fork(
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
pub async fn proxy_summarize(
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

/// POST /tool-approval-mode — set the tool approval mode for a session.
pub async fn proxy_set_approval_mode(
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

/// POST /resume — resume a saved session.
pub async fn proxy_resume(
    State(state): State<Arc<AppState>>,
    Json(req): Json<SessionIdRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .post(
            "/resume",
            &serde_json::json!({"session_id": req.session_id}),
        )
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

/// DELETE /sessions/:id — delete a session.
pub async fn proxy_delete_session(
    State(state): State<Arc<AppState>>,
    axum::extract::Path(id): axum::extract::Path<String>,
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
pub async fn proxy_list_skills(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .get("/skills")
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}
