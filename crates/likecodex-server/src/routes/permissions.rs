use axum::{extract::State, http::StatusCode, response::Json};
use likecodex_core::events::Event;
use likecodex_core::PermissionResponse;
use std::sync::Arc;

use crate::dto::{AnswerRequest, ApproveRequest, AskRespondRequest, PermissionRespondRequest};
use crate::state::AppState;

/// GET /permissions/pending — list all pending permission requests.
pub async fn list_pending_permissions(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .get("/permissions/pending")
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

/// POST /permissions/:id/respond — respond to a permission request.
pub async fn respond_permission(
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

/// GET /ask/pending — list pending ask requests from the agent.
pub async fn proxy_list_pending_asks(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let body = state
        .engine_bridge
        .get("/ask/pending")
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(body))
}

/// POST /ask/:id/respond — respond to an ask request.
pub async fn proxy_respond_ask(
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

/// POST /approve — approve a pending tool call permission request (ACP).
pub async fn proxy_approve(
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

/// POST /answer — answer an ask request from the agent.
pub async fn proxy_answer(
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
