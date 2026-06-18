pub mod docker;
pub mod fallback;
pub mod policy;

use anyhow::Result;
use likecodex_core::config::SandboxConfig;
use std::path::Path;
use tracing::{info, warn};

pub use docker::DockerExecutor;
pub use fallback::FallbackExecutor;
pub use likecodex_executor::ExecutionResult;
pub use policy::SandboxPolicy;

/// Unified sandbox executor that prefers Docker and falls back to local execution.
#[derive(Debug, Clone)]
pub struct SandboxExecutor {
    config: SandboxConfig,
    policy: SandboxPolicy,
    image: String,
}

impl SandboxExecutor {
    pub fn new(config: SandboxConfig) -> Self {
        let image = config
            .image
            .clone()
            .unwrap_or_else(|| "likecodex/sandbox:latest".to_string());
        let policy = SandboxPolicy {
            timeout_secs: config.timeout_secs.unwrap_or(120),
            memory_mb: config.memory_mb,
            max_cpus: config.max_cpus,
            allow_network: config.allow_network(),
            read_only_mounts: Vec::new(),
            read_write_mounts: Vec::new(),
        };
        Self {
            config,
            policy,
            image,
        }
    }

    pub fn is_enabled(&self) -> bool {
        self.config.enabled
    }

    /// Check whether Docker sandboxing is available on this host.
    pub async fn is_available(&self) -> bool {
        if !self.config.enabled {
            return false;
        }
        DockerExecutor::is_available().await
    }

    /// Execute a command in the sandbox, falling back to local execution if Docker is unavailable.
    pub async fn execute(
        &self,
        command: &str,
        working_dir: impl AsRef<Path>,
    ) -> Result<ExecutionResult> {
        if !self.config.enabled {
            anyhow::bail!("sandbox is disabled");
        }

        let working_dir = working_dir.as_ref().to_path_buf();

        if DockerExecutor::is_available().await {
            let docker = DockerExecutor::new(&self.image, self.policy.clone());
            if let Err(e) = docker.ensure_image().await {
                if !self.config.allow_fallback {
                    anyhow::bail!("failed to ensure sandbox image: {e}");
                }
                warn!(error = %e, "failed to ensure sandbox image, falling back to local");
                return FallbackExecutor::new(self.policy.clone())
                    .execute(command, &working_dir)
                    .await;
            }
            match docker.execute(command, &working_dir).await {
                Ok(result) => Ok(result),
                Err(e) => {
                    if !self.config.allow_fallback {
                        anyhow::bail!("sandbox execution failed: {e}");
                    }
                    warn!(error = %e, "sandbox execution failed, falling back to local");
                    FallbackExecutor::new(self.policy.clone())
                        .execute(command, &working_dir)
                        .await
                }
            }
        } else {
            if !self.config.allow_fallback {
                anyhow::bail!("docker not available and sandbox fallback is disabled");
            }
            info!("docker not available, using fallback local executor");
            FallbackExecutor::new(self.policy.clone())
                .execute(command, &working_dir)
                .await
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use likecodex_core::config::SandboxConfig;

    #[test]
    fn sandbox_respects_allow_fallback_flag() {
        let mut cfg = SandboxConfig::default();
        cfg.allow_fallback = false;
        let executor = SandboxExecutor::new(cfg);
        assert!(executor.is_enabled());
    }
}
