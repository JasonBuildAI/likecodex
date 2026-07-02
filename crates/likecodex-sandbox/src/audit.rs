//! Sandbox audit logging — JSON Lines format.
//!
//! Records every sandbox execution as a newline-delimited JSON log entry.
//! This provides a tamper-evident audit trail for compliance and debugging.
//!
//! Log format (`audit.jsonl`):
//! ```json
//! {"timestamp":"2026-07-02T10:00:00Z","session_id":"...","command":"echo hello","exit_code":0,"duration_ms":42,"timed_out":false,"sandbox_type":"docker"}
//! ```

use chrono::Utc;
use serde::Serialize;
use std::path::PathBuf;
use tokio::io::AsyncWriteExt;
use tracing::{debug, warn};

use likecodex_executor::ExecutionResult;

/// A single audit log entry written as a JSON Line.
#[derive(Debug, Clone, Serialize)]
pub struct AuditEntry {
    /// ISO 8601 UTC timestamp.
    pub timestamp: String,
    /// Unique session identifier (UUID v4).
    pub session_id: String,
    /// The command that was executed.
    pub command: String,
    /// Process exit code (None if timed out).
    pub exit_code: Option<i32>,
    /// Whether the command timed out.
    pub timed_out: bool,
    /// Wall-clock duration in milliseconds.
    pub duration_ms: u64,
    /// Stdout character count (not the full content, for size).
    pub stdout_chars: usize,
    /// Stderr character count.
    pub stderr_chars: usize,
    /// Sandbox type: "docker", "local", or "fallback".
    pub sandbox_type: String,
    /// Optional error message if the execution failed structurally.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

/// Audit logger that writes JSON Lines to a file.
#[derive(Debug, Clone)]
pub struct AuditLogger {
    path: PathBuf,
}

impl AuditLogger {
    /// Create a new audit logger writing to the default path
    /// (`{LIKECODEX_DATA_DIR}/audit.jsonl` or `.likecodex/audit.jsonl`).
    pub fn new() -> Result<Self, std::io::Error> {
        let dir = std::env::var("LIKECODEX_DATA_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from(".likecodex"));

        std::fs::create_dir_all(&dir)?;

        Ok(Self {
            path: dir.join("audit.jsonl"),
        })
    }

    /// Create an audit logger with a custom file path.
    pub fn with_path(path: PathBuf) -> Self {
        Self { path }
    }

    /// Return the audit file path.
    pub fn path(&self) -> &std::path::Path {
        &self.path
    }

    /// Log an execution result to the audit trail asynchronously.
    pub async fn log_execution(
        &self,
        result: &ExecutionResult,
        wall_ms: u64,
    ) -> Result<(), std::io::Error> {
        let entry = AuditEntry {
            timestamp: Utc::now().to_rfc3339(),
            session_id: uuid::Uuid::new_v4().to_string(),
            command: result.command.clone(),
            exit_code: result.exit_code,
            timed_out: result.timed_out,
            duration_ms: wall_ms,
            stdout_chars: result.stdout.len(),
            stderr_chars: result.stderr.len(),
            sandbox_type: "docker".to_string(), // caller should update
            error: None,
        };

        self.write_entry(&entry).await
    }

    /// Log a raw audit entry.
    pub async fn log_entry(&self, entry: &AuditEntry) -> Result<(), std::io::Error> {
        self.write_entry(entry).await
    }

    /// Serialize an entry as JSON and append it to the audit log file.
    async fn write_entry(&self, entry: &AuditEntry) -> Result<(), std::io::Error> {
        let line = match serde_json::to_string(entry) {
            Ok(s) => s,
            Err(e) => {
                warn!("audit serialization failed: {e}");
                return Err(std::io::Error::new(
                    std::io::ErrorKind::InvalidData,
                    e.to_string(),
                ));
            }
        };

        let mut file = tokio::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)
            .await?;

        file.write_all(line.as_bytes()).await?;
        file.write_all(b"\n").await?;
        file.flush().await?;

        debug!(path = %self.path.display(), "audit entry written");
        Ok(())
    }

    /// Read all audit entries from the log file.
    pub async fn read_all(&self) -> Result<Vec<AuditEntry>, std::io::Error> {
        let content = tokio::fs::read_to_string(&self.path).await?;
        let mut entries = Vec::new();

        for line in content.lines() {
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }
            match serde_json::from_str::<AuditEntry>(trimmed) {
                Ok(entry) => entries.push(entry),
                Err(e) => warn!("failed to parse audit entry: {e}"),
            }
        }

        Ok(entries)
    }

    /// Get the total number of audit entries.
    pub async fn count(&self) -> usize {
        self.read_all().await.map(|e| e.len()).unwrap_or(0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use likecodex_executor::ExecutionResult;

    #[tokio::test]
    async fn test_audit_roundtrip() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test_audit.jsonl");
        let logger = AuditLogger::with_path(path.clone());

        let result = ExecutionResult {
            command: "echo hello".to_string(),
            stdout: "hello\n".to_string(),
            stderr: String::new(),
            exit_code: Some(0),
            timed_out: false,
            duration_ms: 10,
        };

        logger.log_execution(&result, 12).await.unwrap();

        let entries = logger.read_all().await.unwrap();
        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0].command, "echo hello");
        assert_eq!(entries[0].exit_code, Some(0));
        assert!(!entries[0].session_id.is_empty());
    }
}
