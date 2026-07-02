use axum::Router;
use tower_http::trace::TraceLayer;

/// Apply HTTP request logging / tracing to the router.
pub fn apply_request_logging(router: Router) -> Router {
    router.layer(TraceLayer::new_for_http())
}
