use axum::{extract::State, http::StatusCode, response::Json};
use likecodex_core::config::Config;
use std::sync::Arc;

use crate::state::AppState;

/// GET /health — simple liveness check.
pub async fn health() -> &'static str {
    "ok"
}

/// GET /doctor — detailed diagnostics including engine reachability and API key config.
pub async fn get_doctor(
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

/// GET /config — returns redacted server configuration.
pub async fn get_config(State(state): State<Arc<AppState>>) -> Json<serde_json::Value> {
    Json(serde_json::to_value(state.config.redacted()).unwrap_or_default())
}

/// GET /metrics — proxies engine metrics.
pub async fn get_metrics(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    state
        .engine_bridge
        .get("/metrics")
        .await
        .map(Json)
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))
}
