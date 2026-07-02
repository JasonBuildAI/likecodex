use anyhow::Result;
use likecodex_executor::ExecutionResult;

/// Minimal audit logger stub.
pub struct AuditLogger;

impl AuditLogger {
    pub fn new() -> Result<Self> {
        Ok(Self)
    }

    pub async fn log_execution(&self, _result: &ExecutionResult, _duration_ms: u64) -> Result<()> {
        Ok(())
    }
}
use anyhow::Result;
use likecodex_executor::ExecutionResult;

/// Minimal audit logger stub.
pub struct AuditLogger;

impl AuditLogger {
    pub fn new() -> Result<Self> {
        Ok(Self)
    }

    pub async fn log_execution(&self, _result: &ExecutionResult, _duration_ms: u64) -> Result<()> {
        Ok(())
    }
}
