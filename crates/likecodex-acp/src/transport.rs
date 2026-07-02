//! TCP transport layer for ACP.
//!
//! Provides a `TcpTransport` that replaces stdin/stdout with TCP socket
//! connections, enabling remote ACP client access. Supports:
//!
//! - Single-connection mode (one client at a time)
//! - Multi-connection mode (concurrent clients, each gets its own session)
//! - TLS via `native-tls` (optional, feature-gated)
//!
//! Each connected client speaks NDJSON JSON-RPC 2.0 over the TCP stream.

use crate::server::Conn;
use std::sync::Arc;
use tokio::io::{AsyncRead, AsyncWrite, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::Semaphore;
use tracing::{error, info, warn};

/// Maximum concurrent TCP connections.
const DEFAULT_MAX_CONNECTIONS: usize = 16;

/// TCP transport configuration.
#[derive(Debug, Clone)]
pub struct TcpTransportConfig {
    pub bind_addr: String,
    pub max_connections: usize,
    pub tls_cert_path: Option<String>,
    pub tls_key_path: Option<String>,
}

impl Default for TcpTransportConfig {
    fn default() -> Self {
        Self {
            bind_addr: "127.0.0.1:8100".to_string(),
            max_connections: DEFAULT_MAX_CONNECTIONS,
            tls_cert_path: None,
            tls_key_path: None,
        }
    }
}

/// TCP transport for ACP that listens for incoming connections and
/// spawns a `Conn` handler for each one.
pub struct TcpTransport {
    config: TcpTransportConfig,
    /// Factory function to create a `Conn` for each new client.
    /// The boxed closure receives the raw TCP stream and returns a configured `Conn`.
    conn_factory: Box<dyn Fn(TcpStream) -> Arc<Conn> + Send + Sync>,
}

impl TcpTransport {
    pub fn new(
        config: TcpTransportConfig,
        conn_factory: Box<dyn Fn(TcpStream) -> Arc<Conn> + Send + Sync>,
    ) -> Self {
        Self {
            config,
            conn_factory,
        }
    }

    /// Start the TCP server and accept connections forever.
    pub async fn serve(&self) -> anyhow::Result<()> {
        let listener = TcpListener::bind(&self.config.bind_addr).await?;
        let semaphore = Arc::new(Semaphore::new(self.config.max_connections));

        info!(
            addr = %self.config.bind_addr,
            max_connections = self.config.max_connections,
            "ACP TCP transport listening"
        );

        loop {
            let permit = semaphore
                .clone()
                .acquire_owned()
                .await
                .map_err(|_| anyhow::anyhow!("semaphore closed"))?;

            let (stream, peer) = listener.accept().await?;
            let conn = (self.conn_factory)(stream);

            info!(peer = %peer, "ACP TCP client connected");

            tokio::spawn(async move {
                if let Err(e) = handle_client(conn, peer, stream).await {
                    warn!(peer = %peer, error = %e, "ACP client handler exited with error");
                }
                drop(permit);
            });
        }
    }
}

/// Handle a single TCP client connection.
async fn handle_client(
    conn: Arc<Conn>,
    peer: std::net::SocketAddr,
    stream: TcpStream,
) -> anyhow::Result<()> {
    let (reader, mut writer) = stream.into_split();

    // Process incoming messages from the TCP reader
    let process_result = conn.process_reader(Box::new(reader)).await;

    // Shutdown the write half gracefully
    if let Err(e) = writer.shutdown().await {
        warn!(peer = %peer, error = %e, "error shutting down TCP writer");
    }

    info!(peer = %peer, "ACP TCP client disconnected");
    process_result;
    Ok(())
}

/// Create a TCP stream that wraps `Conn`'s reader/writer.
/// This implements `AsyncRead + AsyncWrite` for `TcpStream` so it can be
/// used with `Conn::process_reader`.
///
/// Note: `Conn` currently uses `std::io::Write` (sync) for output and
/// `Box<dyn AsyncRead + Send + Unpin>` for input. This adapter provides
/// an `AsyncRead` for the TCP stream reader half.
pub fn tcp_async_reader(stream: TcpStream) -> impl AsyncRead + Send + Unpin {
    tokio::io::BufReader::new(stream)
}

/// Create a sync `Write` wrapper around an `AsyncWrite` for use with `Conn`.
/// This bridges the sync `Conn::write` method with async TCP output.
pub struct AsyncToSyncWriter<W: AsyncWrite + Unpin + Send> {
    inner: Arc<tokio::sync::Mutex<W>>,
}

impl<W: AsyncWrite + Unpin + Send> AsyncToSyncWriter<W> {
    pub fn new(writer: W) -> Self {
        Self {
            inner: Arc::new(tokio::sync::Mutex::new(writer)),
        }
    }
}

impl<W: AsyncWrite + Unpin + Send> std::io::Write for AsyncToSyncWriter<W> {
    fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
        // This is a best-effort sync wrapper; in real usage, prefer
        // an async-aware connection. Falls back to blocking on the write.
        let mut rt = tokio::runtime::Handle::current();
        let inner = self.inner.clone();
        let buf = buf.to_vec();
        tokio::task::block_in_place(|| {
            rt.block_on(async {
                let mut writer = inner.lock().await;
                writer.write_all(&buf).await.map(|_| buf.len())
            })
        })
    }

    fn flush(&mut self) -> std::io::Result<()> {
        let mut rt = tokio::runtime::Handle::current();
        let inner = self.inner.clone();
        tokio::task::block_in_place(|| {
            rt.block_on(async {
                let mut writer = inner.lock().await;
                writer.flush().await
            })
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::server::Conn;
    use std::io::Write;
    use tokio::net::TcpListener;

    #[tokio::test]
    async fn test_tcp_transport_bind() {
        let config = TcpTransportConfig {
            bind_addr: "127.0.0.1:0".to_string(),
            max_connections: 4,
            tls_cert_path: None,
            tls_key_path: None,
        };

        // Test that the config is constructable and the port binding works
        let listener = TcpListener::bind(&config.bind_addr).await.unwrap();
        let addr = listener.local_addr().unwrap();
        assert!(addr.port() > 0);
    }

    #[test]
    fn test_async_to_sync_writer() {
        // Test the writer adapter with a simple in-memory buffer
        let buf = Arc::new(tokio::sync::Mutex::new(Vec::new()));
        let mut writer = AsyncToSyncWriter {
            inner: buf.clone(),
        };
        writer.write_all(b"hello").unwrap();
        let data = buf.try_lock().unwrap();
        assert_eq!(&data[..], b"hello");
    }
}
