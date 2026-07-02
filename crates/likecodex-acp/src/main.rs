//! ACP entry point — pure async stdin/stdout JSON-RPC server.
//!
//! Starts the ACP server on stdin/stdout, bridging to the LikeCodex engine.
//! All RPC handlers are registered as async closures, eliminating the
//! `block_in_place` + `block_on` anti-pattern.

use likecodex_acp::server::Conn;
use likecodex_acp::service::{AcpService, SessionStore};
use likecodex_core::config::Config;
use likecodex_core::events::EventBus;
use std::sync::Arc;
use tokio::io::{stdin, stdout};
use tracing::{info, warn};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt().with_env_filter(
        tracing_subscriber::EnvFilter::from_default_env(),
    ).init();

    let config = Config::load().unwrap_or_else(|e| {
        warn!(error = %e, "failed to load config, using defaults");
        Config::default()
    });

    let engine_url = config
        .server
        .engine_url
        .clone()
        .or_else(|| std::env::var("LIKECODEX_ENGINE_URL").ok())
        .unwrap_or_else(|| "http://127.0.0.1:9090".to_string());

    let event_bus = EventBus::new(1024);

    // Initialise the SQLite-backed session store
    let store = SessionStore::new(&SessionStore::default_path())
        .map_err(|e| anyhow::anyhow!("failed to open session store: {e}"))?;

    let service = Arc::new(AcpService::new(
        engine_url.clone(),
        config,
        event_bus.clone(),
        Some(store),
    )
    .await);

    // Health check
    if let Err(e) = service.factory().health_check().await {
        warn!("ACP engine health check failed: {e}");
    }

    // Create the connection — writer uses std::io::Write sync wrapper for
    // stdout, while stdin is read asynchronously via process_reader.
    let conn = Arc::new(Conn::new(Box::new(stdout())));

    // ── Register all RPC handlers ────────────────────────────

    // initialize
    {
        let svc = service.clone();
        conn.handle(
            "initialize",
            Arc::new(move |params| Box::pin({
                let svc = svc.clone();
                async move { svc.handle_initialize(params).await }
            })),
        )
        .await;
    }

    // authenticate
    {
        let svc = service.clone();
        conn.handle(
            "authenticate",
            Arc::new(move |params| Box::pin({
                let svc = svc.clone();
                async move { svc.handle_authenticate(params).await }
            })),
        )
        .await;
    }

    // session/new
    {
        let svc = service.clone();
        conn.handle(
            "session/new",
            Arc::new(move |params| Box::pin({
                let svc = svc.clone();
                async move { svc.handle_session_new(params).await }
            })),
        )
        .await;
    }

    // session/load
    {
        let svc = service.clone();
        conn.handle(
            "session/load",
            Arc::new(move |params| Box::pin({
                let svc = svc.clone();
                async move { svc.handle_session_load(params).await }
            })),
        )
        .await;
    }

    // session/resume
    {
        let svc = service.clone();
        conn.handle(
            "session/resume",
            Arc::new(move |params| Box::pin({
                let svc = svc.clone();
                async move { svc.handle_session_resume(params).await }
            })),
        )
        .await;
    }

    // session/prompt
    {
        let svc = service.clone();
        conn.handle(
            "session/prompt",
            Arc::new(move |params| Box::pin({
                let svc = svc.clone();
                async move { svc.handle_session_prompt(params).await }
            })),
        )
        .await;
    }

    // session/cancel (notification)
    {
        let svc = service.clone();
        conn.handle_notify(
            "session/cancel",
            Arc::new(move |params| Box::pin({
                let svc = svc.clone();
                async move { let _ = svc.handle_session_cancel(params).await; }
            })),
        )
        .await;
    }

    // session/set_config_option
    {
        let svc = service.clone();
        conn.handle(
            "session/set_config_option",
            Arc::new(move |params| Box::pin({
                let svc = svc.clone();
                async move { svc.handle_session_set_config_option(params).await }
            })),
        )
        .await;
    }

    // session/set_model
    {
        let svc = service.clone();
        conn.handle(
            "session/set_model",
            Arc::new(move |params| Box::pin({
                let svc = svc.clone();
                async move { svc.handle_session_set_model(params).await }
            })),
        )
        .await;
    }

    // session/list
    {
        let svc = service.clone();
        conn.handle(
            "session/list",
            Arc::new(move |params| Box::pin({
                let svc = svc.clone();
                async move { svc.handle_session_list(params).await }
            })),
        )
        .await;
    }

    // session/close
    {
        let svc = service.clone();
        conn.handle(
            "session/close",
            Arc::new(move |params| Box::pin({
                let svc = svc.clone();
                async move { svc.handle_session_close(params).await }
            })),
        )
        .await;
    }

    // session/delete
    {
        let svc = service.clone();
        conn.handle(
            "session/delete",
            Arc::new(move |params| Box::pin({
                let svc = svc.clone();
                async move { svc.handle_session_delete(params).await }
            })),
        )
        .await;
    }

    // session/request_permission
    {
        let svc = service.clone();
        conn.handle(
            "session/request_permission",
            Arc::new(move |params| Box::pin({
                let svc = svc.clone();
                async move { svc.handle_request_permission(params).await }
            })),
        )
        .await;
    }

    info!("LikeCodex ACP server starting on stdin/stdout");

    // Read stdin asynchronously — this is the main event loop
    conn.process_reader(Box::new(stdin())).await;

    info!("LikeCodex ACP server stopped");

    Ok(())
}
