pub mod docker;
pub mod fallback;
pub mod policy;

use anyhow::Result;
use likecodex_core::config::SandboxConfig;
use std::path::Path;
use std::sync::OnceLock;
use tokio::sync::Mutex;
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
    /// Result is cached after first check, refreshed every 30 seconds.
    pub async fn is_available(&self) -> bool {
        if !self.config.enabled {
            return false;
        }
        static AVAILABLE: OnceLock<Mutex<(bool, tokio::time::Instant)>> = OnceLock::new();
        let cache = AVAILABLE.get_or_init(|| Mutex::new((false, tokio::time::Instant::now())));
        let mut guard = cache.lock().await;
        if guard.1.elapsed() < tokio::time::Duration::from_secs(30) {
            return guard.0;
        }
        let available = DockerExecutor::is_available().await;
        *guard = (available, tokio::time::Instant::now());
        available
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

        if self.is_available().await {
            let docker = DockerExecutor::new(&self.image, self.policy.clone());
            if let Err(e) = docker.ensure_image().await {
                if !self.config.allow_fallback {
                    anyhow::bail!("sandbox required but Docker image not available: {e}");
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
                        anyhow::bail!("sandbox required but execution failed: {e}");
                    }
                    warn!(error = %e, "sandbox execution failed, falling back to local");
                    FallbackExecutor::new(self.policy.clone())
                        .execute(command, &working_dir)
                        .await
                }
            }
        } else if self.config.allow_fallback {
            info!("docker not available, using fallback local executor");
            FallbackExecutor::new(self.policy.clone())
                .execute(command, &working_dir)
                .await
        } else {
            anyhow::bail!("sandbox execution is required but Docker is not available");
        }
    }
}
