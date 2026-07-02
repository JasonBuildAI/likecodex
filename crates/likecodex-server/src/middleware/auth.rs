use axum::http::{header, HeaderMap, StatusCode};
use likecodex_core::config::Config;

/// Validate Bearer token from Authorization header against the server's API token.
/// Returns `Ok(())` if no token is configured or the token matches.
pub fn authorize_execute(headers: &HeaderMap, config: &Config) -> Result<(), (StatusCode, String)> {
    let Some(expected) = config.server.api_token.as_ref() else {
        return Ok(());
    };
    let auth = headers
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    let token = auth.strip_prefix("Bearer ").unwrap_or("");
    if token == expected {
        Ok(())
    } else {
        Err((
            StatusCode::UNAUTHORIZED,
            "invalid or missing API token".to_string(),
        ))
    }
}
