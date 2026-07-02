use axum::{
    extract::ws::{Message, WebSocket, WebSocketUpgrade},
    extract::{Path, State},
    http::StatusCode,
    response::Json,
};
use futures::StreamExt;
use std::sync::Arc;

use crate::dto::NewSessionRequest;
use crate::pty::PtyManager;
use crate::state::AppState;

/// POST /api/terminal/create — create a new PTY terminal session.
pub async fn pty_create(
    State(state): State<Arc<AppState>>,
    Json(req): Json<NewSessionRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<serde_json::Value>)> {
    let session_id = uuid::Uuid::new_v4().to_string();
    let cwd = req.cwd.unwrap_or_else(|| ".".to_string());
    PtyManager::create_session(&state.pty_manager, session_id.clone(), cwd)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({"error": e.to_string()})),
            )
        })?;
    Ok(Json(serde_json::json!({"sessionId": session_id})))
}

/// POST /api/terminal/:id/close — close a terminal session.
pub async fn pty_close(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Json<serde_json::Value> {
    let ok = state.pty_manager.close_session(&id).await;
    Json(serde_json::json!({"closed": ok}))
}

/// GET /api/terminal/list — list active terminal sessions.
pub async fn pty_list(
    State(state): State<Arc<AppState>>,
) -> Json<serde_json::Value> {
    let sessions = state.pty_manager.list_sessions().await;
    Json(serde_json::json!({"sessions": sessions}))
}

/// POST /api/terminal/:id/resize — resize a terminal (rows, cols).
pub async fn pty_resize(
    Path(id): Path<String>,
    Json(body): Json<serde_json::Value>,
) -> Json<serde_json::Value> {
    let rows = body["rows"].as_u64().unwrap_or(24) as u16;
    let cols = body["cols"].as_u64().unwrap_or(80) as u16;
    Json(serde_json::json!({"resized": true, "rows": rows, "cols": cols}))
}

/// GET /api/terminal/:id/ws — WebSocket endpoint for terminal I/O.
pub async fn pty_ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<axum::response::Response, (StatusCode, Json<serde_json::Value>)> {
    let pty = state.pty_manager.clone();
    let session_id = id.clone();

    Ok(ws.on_upgrade(move |socket| handle_pty_ws(socket, pty, session_id)))
}

async fn handle_pty_ws(mut ws: WebSocket, pty: PtyManager, session_id: String) {
    // Try to get the stdin sender for this session
    let stdin_tx = match pty.get_session(&session_id).await {
        Some(tx) => tx,
        None => {
            let _ = ws
                .send(Message::Text("ERROR: session not found".into()))
                .await;
            return;
        }
    };

    // Split WebSocket into sender/receiver
    let (mut ws_sender, mut ws_receiver) = ws.split();

    // Task: forward messages from WebSocket to the PTY stdin
    let tx = stdin_tx.clone();
    let forward_task = tokio::spawn(async move {
        while let Some(Ok(msg)) = ws_receiver.next().await {
            match msg {
                Message::Text(text) if !text.is_empty() => {
                    let _ = tx.send(format!("{}\n", text)).await;
                }
                Message::Binary(_) => {}
                Message::Close(_) => break,
                _ => {}
            }
        }
    });

    // Acknowledge the WebSocket connection
    let _ = ws_sender
        .send(Message::Text("Connected to PTY session".into()))
        .await;

    // Wait for the forward task to finish
    let _ = forward_task.await;
}
