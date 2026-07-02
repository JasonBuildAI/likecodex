//! NDJSON JSON-RPC 2.0 transport layer.
//!
//! Handles stdin/stdout connection management, request/response
//! pairing, and notification dispatch for the ACP protocol.

use serde::Serialize;
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use tokio::sync::oneshot;
use tracing::{debug, error, warn};

/// Maximum message size (32 MiB).
const MAX_MESSAGE_BYTES: usize = 32 * 1024 * 1024;

/// Handler for an incoming JSON-RPC request.
pub type RequestHandler = Arc<
    dyn Fn(serde_json::Value) -> Result<serde_json::Value, RpcErrorBox> + Send + Sync,
>;

/// Handler for an incoming JSON-RPC notification.
pub type NotificationHandler = Arc<dyn Fn(serde_json::Value) + Send + Sync>;

/// A boxed RPC error compatible with the protocol.
#[derive(Debug, Clone)]
pub struct RpcErrorBox {
    pub code: i32,
    pub message: String,
    pub data: Option<serde_json::Value>,
}

impl RpcErrorBox {
    pub fn new(code: i32, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
            data: None,
        }
    }
}

/// An NDJSON JSON-RPC 2.0 connection.
pub struct Conn {
    writer: Arc<Mutex<Box<dyn Write + Send>>>,
    next_id: AtomicU64,
    pending: Arc<Mutex<HashMap<u64, oneshot::Sender<serde_json::Value>>>>,
    request_handlers: Arc<Mutex<HashMap<String, RequestHandler>>>,
    notification_handlers: Arc<Mutex<HashMap<String, NotificationHandler>>>,
}

impl Conn {
    /// Create a new connection from reader/writer pair.
    pub fn new(
        _reader: Box<dyn std::io::Read + Send>,
        writer: Box<dyn Write + Send>,
    ) -> Self {
        Self {
            writer: Arc::new(Mutex::new(writer)),
            next_id: AtomicU64::new(1),
            pending: Arc::new(Mutex::new(HashMap::new())),
            request_handlers: Arc::new(Mutex::new(HashMap::new())),
            notification_handlers: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    fn lock_mutex<T>(lock: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
        lock.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// Register a request handler for a method.
    pub fn handle(&self, method: impl Into<String>, handler: RequestHandler) {
        let mut handlers = self.request_handlers.lock().unwrap();
        handlers.insert(method.into(), handler);
    }

    /// Register a notification handler for a method.
    pub fn handle_notify(&self, method: impl Into<String>, handler: NotificationHandler) {
        let mut handlers = self.notification_handlers.lock().unwrap();
        handlers.insert(method.into(), handler);
    }

    /// Send a fire-and-forget notification.
    pub fn notify(&self, method: &str, params: impl Serialize) {
        let msg = serde_json::json!({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        });
        self.write(&msg);
    }

    /// Send a request and wait for the response.
    pub async fn request(
        &self,
        method: &str,
        params: impl Serialize,
    ) -> Result<serde_json::Value, RpcErrorBox> {
        let id = self.next_id.fetch_add(1, Ordering::SeqCst);
        let msg = serde_json::json!({
            "jsonrpc": "2.0",
            "id": id,
            "method": method,
            "params": params,
        });

        let (tx, rx) = oneshot::channel();
        {
            let mut pending = Self::lock_mutex(&self.pending);
            pending.insert(id, tx);
        }

        self.write(&msg);

        match rx.await {
            Ok(result) => Ok(result),
            Err(_) => Err(RpcErrorBox::new(
                crate::protocol::ERR_INTERNAL,
                "request cancelled",
            )),
        }
    }

    /// Write a JSON value to the output stream.
    fn write(&self, value: &serde_json::Value) {
        let mut writer = Self::lock_mutex(&self.writer);
        let line = serde_json::to_string(value).unwrap_or_else(|e| {
            error!("JSON serialization error: {e}");
            "{}".to_string()
        });
        let _ = writeln!(writer, "{line}");
        let _ = writer.flush();
    }

    /// Write an error response.
    fn write_error(&self, id: Option<serde_json::Value>, code: i32, message: &str) {
        let error = serde_json::json!({
            "jsonrpc": "2.0",
            "id": id,
            "error": {
                "code": code,
                "message": message,
            }
        });
        self.write(&error);
    }

    /// Process incoming messages from the reader.
    pub fn process_reader(&self, reader: Box<dyn std::io::Read + Send>) {
        let mut buf_reader = BufReader::with_capacity(MAX_MESSAGE_BYTES, reader);
        let mut line = String::new();

        loop {
            line.clear();
            match buf_reader.read_line(&mut line) {
                Ok(0) => {
                    debug!("ACP connection closed (EOF)");
                    break;
                }
                Ok(_) => {
                    let trimmed = line.trim();
                    if trimmed.is_empty() {
                        continue;
                    }
                    self.dispatch(trimmed);
                }
                Err(e) => {
                    error!("ACP read error: {e}");
                    break;
                }
            }
        }

        // Clean up pending requests on disconnect
        {
            let mut pending = Self::lock_mutex(&self.pending);
            let count = pending.len();
            pending.clear();
            if count > 0 {
                debug!("ACP discarded {count} pending request(s) on disconnect");
            }
        }
    }

    /// Dispatch a single JSON-RPC message.
    fn dispatch(&self, line: &str) {
        let msg: serde_json::Value = match serde_json::from_str(line) {
            Ok(v) => v,
            Err(e) => {
                warn!("ACP parse error: {e}");
                self.write_error(None, crate::protocol::ERR_PARSE, &e.to_string());
                return;
            }
        };

        let id = msg.get("id").cloned();
        let method = msg.get("method").and_then(|m| m.as_str()).map(|s| s.to_string());

        match (id, method) {
            // Request
            (Some(id), Some(method)) => {
                let params = msg.get("params").cloned().unwrap_or(serde_json::Value::Null);
                let handlers = Self::lock_mutex(&self.request_handlers);
                if let Some(handler) = handlers.get(&method) {
                    match handler(params) {
                        Ok(result) => {
                            let response = serde_json::json!({
                                "jsonrpc": "2.0",
                                "id": id,
                                "result": result,
                            });
                            self.write(&response);
                        }
                        Err(e) => {
                            self.write_error(
                                Some(id),
                                e.code,
                                &e.message,
                            );
                        }
                    }
                } else {
                    self.write_error(
                        Some(id),
                        crate::protocol::ERR_METHOD_NOT_FOUND,
                        &format!("method not found: {method}"),
                    );
                }
            }
            // Notification
            (None, Some(method)) => {
                let params = msg.get("params").cloned().unwrap_or(serde_json::Value::Null);
                let handlers = Self::lock_mutex(&self.notification_handlers);
                if let Some(handler) = handlers.get(&method) {
                    handler(params);
                }
            }
            // Response
            (Some(id), None) => {
                if let Some(id_num) = id.as_u64() {
                    let mut pending = Self::lock_mutex(&self.pending);
                    if let Some(tx) = pending.remove(&id_num) {
                        if let Some(error) = msg.get("error") {
                            let _ = tx.send(serde_json::json!({ "error": error }));
                        } else {
                            let result = msg.get("result").cloned().unwrap_or(serde_json::Value::Null);
                            let _ = tx.send(result);
                        }
                    }
                }
            }
            // Invalid
            (None, None) => {
                self.write_error(None, crate::protocol::ERR_INVALID_REQUEST, "missing method or id");
            }
        }
    }
}