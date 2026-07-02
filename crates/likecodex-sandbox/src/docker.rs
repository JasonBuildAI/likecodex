use anyhow::{Context, Result};
use std::path::Path;
use std::process::Stdio;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;
use tokio::time::{timeout, Duration};
use tracing::{debug, info, warn};

use crate::policy::SandboxPolicy;
use crate::ExecutionResult;

/// Docker-based sandbox executor.
#[derive(Debug, Clone)]
pub struct DockerExecutor {
    image: String,
    policy: SandboxPolicy,
}

impl DockerExecutor {
    pub fn new(image: impl Into<String>, policy: SandboxPolicy) -> Self {
        Self {
            image: image.into(),
            policy,
        }
    }

    /// Check whether the Docker CLI is available and responsive.
    pub async fn is_available() -> bool {
        match Command::new("docker")
            .arg("--version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .await
        {
            Ok(status) => status.success(),
            Err(e) => {
                debug!(error = %e, "docker not available");
                false
            }
        }
    }

    /// Build the sandbox image from the bundled Dockerfile if it does not exist locally.
    pub async fn ensure_image(&self) -> Result<()> {
        let exists = self.image_exists().await?;
        if exists {
            debug!(image = %self.image, "sandbox image already exists");
            return Ok(());
        }

        info!(image = %self.image, "building sandbox image");
        let mut cmd = Command::new("docker");
        cmd.arg("build")
            .arg("-t")
            .arg(&self.image)
            .arg("docker/sandbox");

        let status = cmd
            .current_dir(".")
            .status()
            .await
            .context("failed to spawn docker build")?;

        if !status.success() {
            anyhow::bail!("docker build failed with status {status:?}");
        }
        Ok(())
    }

    async fn image_exists(&self) -> Result<bool> {
        let output = Command::new("docker")
            .args(["images", "-q", &self.image])
            .output()
            .await
            .context("failed to list docker images")?;
        Ok(!output.stdout.is_empty())
    }

    fn build_resource_args(&self) -> Vec<String> {
        let mut args = Vec::new();

        // Memory limit
        if let Some(mem) = self.policy.memory_mb {
            args.push("--memory".to_string());
            args.push(format!("{mem}m"));
            args.push("--memory-swap".to_string());
            args.push(format!("{mem}m")); // no swap
        }

        // CPU limit
        if let Some(cpus) = self.policy.max_cpus {
            args.push("--cpus".to_string());
            args.push(cpus.to_string());
        }

        // Process limit (prevents fork bombs)
        args.push("--pids-limit".to_string());
        args.push("100".to_string());

        // File descriptor limit
        args.push("--ulimit".to_string());
        args.push("nofile=1024:2048".to_string());

        // Security: drop all capabilities
        args.push("--security-opt".to_string());
        args.push("no-new-privileges:true".to_string());
        args.push("--cap-drop".to_string());
        args.push("ALL".to_string());
        args.push("--cap-add".to_string());
        args.push("DAC_OVERRIDE".to_string());
        args.push("--cap-add".to_string());
        args.push("CHOWN".to_string());

        // Read-only root filesystem
        args.push("--read-only".to_string());

        args
    }

    /// Run a command inside a fresh sandbox container.
    pub async fn execute(
        &self,
        command: &str,
        working_dir: impl AsRef<Path>,
    ) -> Result<ExecutionResult> {
        let working_dir = working_dir
            .as_ref()
            .canonicalize()
            .context("failed to canonicalize working directory for docker mount")?;
        let start = std::time::Instant::now();

        let mut docker_args = vec![
            "run".to_string(),
            "--rm".to_string(),
            "--network".to_string(),
            if self.policy.allow_network {
                "bridge".to_string()
            } else {
                "none".to_string()
            },
        ];

        // Apply resource limits and security hardening
        docker_args.append(&mut self.build_resource_args());

        // Mount the project directory. By default read-write for the workspace.
        let mount_path = working_dir.to_string_lossy().to_string();
        // Use bind mount with correct quoting for path spaces
        let mount = format!("{}:/workspace", mount_path);
        docker_args.push("-v".to_string());
        docker_args.push(mount);
        docker_args.push("-w".to_string());
        docker_args.push("/workspace".to_string());

        docker_args.push(self.image.clone());
        docker_args.push("sh".to_string());
        docker_args.push("-c".to_string());
        docker_args.push(command.to_string());

        info!(command = %command, image = %self.image, "executing in docker sandbox");
        let mut child = Command::new("docker")
            .args(&docker_args)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true)
            .spawn()
            .context("failed to spawn docker run")?;

        let stdout = child.stdout.take().context("missing stdout")?;
        let stderr = child.stderr.take().context("missing stderr")?;
        let mut stdout_reader = BufReader::new(stdout).lines();
        let mut stderr_reader = BufReader::new(stderr).lines();

        let mut stdout_lines = Vec::new();
        let mut stderr_lines = Vec::new();

        let result = timeout(Duration::from_secs(self.policy.timeout_secs), async {
            loop {
                tokio::select! {
                    line = stdout_reader.next_line() => {
                        match line {
                            Ok(Some(l)) => stdout_lines.push(l),
                            Ok(None) => break,
                            Err(e) => {
                                warn!(error = %e, "error reading stdout");
                                break;
                            }
                        }
                    }
                    line = stderr_reader.next_line() => {
                        match line {
                            Ok(Some(l)) => stderr_lines.push(l),
                            Ok(None) => {}
                            Err(e) => {
                                warn!(error = %e, "error reading stderr");
                            }
                        }
                    }
                }
            }
            child.wait().await
        })
        .await;

        let (exit_code, timed_out) = match result {
            Ok(Ok(status)) => (status.code(), false),
            Ok(Err(e)) => return Err(anyhow::anyhow!("docker run failed: {e}")),
            Err(_) => {
                let _ = child.kill().await;
                let _ = child.wait().await;
                (None, true)
            }
        };

        let result = ExecutionResult {
            command: command.to_string(),
            stdout: stdout_lines.join("\n"),
            stderr: stderr_lines.join("\n"),
            exit_code,
            timed_out,
            duration_ms: start.elapsed().as_millis() as u64,
        };

        if result.timed_out {
            warn!(command = %command, "sandbox command timed out");
        } else if result.exit_code.unwrap_or(1) != 0 {
            warn!(command = %command, exit_code = ?result.exit_code, "sandbox command failed");
        } else {
            info!(command = %command, "sandbox command succeeded");
        }

        Ok(result)
    }
}
