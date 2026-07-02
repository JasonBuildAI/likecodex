use likecodex_core::config::Config;
use likecodex_core::events::EventBus;

use crate::engine_bridge::EngineBridge;
use crate::pty::PtyManager;

/// Application-wide shared state injected into all Axum route handlers.
pub struct AppState {
    pub config: Config,
    pub event_bus: EventBus,
    pub engine_bridge: EngineBridge,
    pub pty_manager: PtyManager,
}

impl AppState {
    pub fn new(
        config: Config,
        event_bus: EventBus,
        engine_bridge: EngineBridge,
        pty_manager: PtyManager,
    ) -> Self {
        Self {
            config,
            event_bus,
            engine_bridge,
            pty_manager,
        }
    }
}
