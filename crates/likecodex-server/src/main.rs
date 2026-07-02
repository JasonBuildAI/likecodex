mod engine_bridge;
mod event_mapping;
mod pty;

mod state;
mod dto;
mod routes;
mod middleware;

use likecodex_core::config::Config;
use likecodex_core::events::EventBus;
use std::sync::Arc;
use tracing::{info, warn};

use crate::engine_bridge::EngineBridge;
use crate::pty::PtyManager;
use crate::routes::configure_routes;
use crate::state::AppState;

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
    let state = Arc::new(AppState::new(
        config.clone(),
        event_bus,
        engine_bridge,
        PtyManager::new(),
    ));

    let app = configure_routes(state);

    let host = config.server.host.clone();
    let port = config.server.port;
    let listener = tokio::net::TcpListener::bind(format!("{host}:{port}")).await?;
    info!(host = %host, port = %port, "LikeCodex server listening");
    axum::serve(listener, app).await?;
    Ok(())
}
