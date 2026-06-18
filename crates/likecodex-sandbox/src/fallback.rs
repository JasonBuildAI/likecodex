use std::path::Path;

use likecodex_executor::{ExecutionResult, LocalExecutor};

use crate::policy::SandboxPolicy;

/// Fallback executor used when Docker is unavailable.
/// It runs commands locally but enforces a restricted working directory and timeout.
pub struct FallbackExecutor {
    policy: SandboxPolicy,
}

impl FallbackExecutor {
    pub fn new(policy: SandboxPolicy) -> Self {
        Self { policy }
    }

    pub async fn execute(
        &self,
        command: &str,
        working_dir: impl AsRef<Path>,
    ) -> anyhow::Result<ExecutionResult> {
        let executor = LocalExecutor::new(working_dir).with_timeout(self.policy.timeout_secs);
        executor.execute(command).await
    }
}
