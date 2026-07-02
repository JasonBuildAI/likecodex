//! ACP entry point.
//!
//! Starts the ACP server on stdin/stdout, bridging to the LikeCodex engine.

use likecodex_acp::server::Conn;
use likecodex_acp::service::AcpService;
use likecodex_core::config::Config;
use likecodex_core::events::EventBus;
use std::io::{stdin, stdout};
use std::sync::Arc;
use tracing::{info, warn};
use tracing_subscriber;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

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
    let service = Arc::new(AcpService::new(engine_url, config, event_bus));

    // Health check
    if let Err(e) = service.factory().health_check().await {
        warn!("ACP engine health check failed: {e}");
    }

    let conn = Arc::new(Conn::new(Box::new(stdin()), Box::new(stdout())));

    // Register initialize handler
    {
        let svc = service.clone();
        conn.handle("initialize", Arc::new(move |params| {
            let svc = svc.clone();
            tokio::task::block_in_place(|| {
                tokio::runtime::Handle::current().block_on(async {
                    svc.handle_initialize(params).await
                })
            })
        }));
    }

    // Register authenticate handler
    {
        let svc = service.clone();
        conn.handle("authenticate", Arc::new(move |params| {
            let svc = svc.clone();
            tokio::task::block_in_place(|| {
                tokio::runtime::Handle::current().block_on(async {
                    svc.handle_authenticate(params).await
                })
            })
        }));
    }

    // Register session/new handler
    {
        let svc = service.clone();
        conn.handle("session/new", Arc::new(move |params| {
            let svc = svc.clone();
            tokio::task::block_in_place(|| {
                tokio::runtime::Handle::current().block_on(async {
                    svc.handle_session_new(params).await
                })
            })
        }));
    }

    // Register session/load handler
    {
        let svc = service.clone();
        conn.handle("session/load", Arc::new(move |params| {
            let svc = svc.clone();
            tokio::task::block_in_place(|| {
                tokio::runtime::Handle::current().block_on(async {
                    svc.handle_session_load(params).await
                })
            })
        }));
    }

    // Register session/resume handler
    {
        let svc = service.clone();
        conn.handle("session/resume", Arc::new(move |params| {
            let svc = svc.clone();
            tokio::runtime::Handle::current().block_on(async {
                svc.handle_session_resume(params).await
            })
        }));
    }

    // Register session/prompt handler
    {
        let svc = service.clone();
        conn.handle("session/prompt", Arc::new(move |params| {
            let svc = svc.clone();
            tokio::task::block_in_place(|| {
                tokio::runtime::Handle::current().block_on(async {
                    svc.handle_session_prompt(params).await
                })
            })
        }));
    }

    // Register session/cancel handler (as notification)
    {
        let svc = service.clone();
        conn.handle_notify("session/cancel", Arc::new(move |params| {
            let svc = svc.clone();
            tokio::task::block_in_place(|| {
                tokio::runtime::Handle::current().block_on(async {
                    let _ = svc.handle_session_cancel(params).await;
                })
            })
        }));
    }

    // Register session/set_config_option handler
    {
        let svc = service.clone();
        conn.handle("session/set_config_option", Arc::new(move |params| {
            let svc = svc.clone();
            tokio::task::block_in_place(|| {
                tokio::runtime::Handle::current().block_on(async {
                    svc.handle_session_set_config_option(params).await
                })
            })
        }));
    }

    // Register session/set_model handler
    {
        let svc = service.clone();
        conn.handle("session/set_model", Arc::new(move |params| {
            let svc = svc.clone();
            tokio::task::block_in_place(|| {
                tokio::runtime::Handle::current().block_on(async {
                    svc.handle_session_set_model(params).await
                })
            })
        }));
    }

    // Register session/list handler
    {
        let svc = service.clone();
        conn.handle("session/list", Arc::new(move |params| {
            let svc = svc.clone();
            tokio::runtime::Handle::current().block_on(async {
                svc.handle_session_list(params).await
            })
        }));
    }

    // Register session/close handler
    {
        let svc = service.clone();
        conn.handle("session/close", Arc::new(move |params| {
            let svc = svc.clone();
            tokio::runtime::Handle::current().block_on(async {
                svc.handle_session_close(params).await
            })
        }));
    }

    // Register session/delete handler
    {
        let svc = service.clone();
        conn.handle("session/delete", Arc::new(move |params| {
            let svc = svc.clone();
            tokio::runtime::Handle::current().block_on(async {
                svc.handle_session_delete(params).await
            })
        }));
    }

    info!("LikeCodex ACP server starting on stdin/stdout");
    conn.process_reader(Box::new(stdin()));
    info!("LikeCodex ACP server stopped");

    Ok(())
}