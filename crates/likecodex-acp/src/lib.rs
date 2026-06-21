//! LikeCodex ACP (Agent Client Protocol) implementation.
//!
//! Provides a stdio-based JSON-RPC 2.0 interface for editor integration,
//! following the ACP v1 specification.

pub mod dispatch;
pub mod protocol;
pub mod server;
pub mod service;