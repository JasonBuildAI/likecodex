use anyhow::{Context, Result};
use likecodex_core::events::{Event, EventBus};
use std::path::Path;
use std::process::Stdio;
use std::time::Duration;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;
use tokio::time::timeout;
use tracing::{debug, error, info};

/// Result of a command execution.
#[derive(Debug, Clone)]
pub struct ExecutionResult {
    pub command: String,
    pub stdout: String,
    pub stderr: String,
    pub exit_code: Option<i32>,
    pub timed_out: bool,
    pub duration_ms: u64,
}

/// Executor that runs shell commands locally within a working directory.
#[derive(Debug, Clone)]
pub struct LocalExecutor {
    working_dir: std::path::PathBuf,
    timeout: Duration,
    event_bus: Option<EventBus>,
}

impl LocalExecutor {
    pub fn new(working_dir: impl AsRef<Path>) -> Self {
        Self {
            working_dir: working_dir.as_ref().to_path_buf(),
            timeout: Duration::from_secs(120),
            event_bus: None,
        }
    }

    pub fn with_timeout(mut self, seconds: u64) -> Self {
        self.timeout = Duration::from_secs(seconds);
        self
    }

    pub fn with_event_bus(mut self, bus: EventBus) -> Self {
        self.event_bus = Some(bus);
        self
    }

    pub async fn execute(&self, command: &str) -> Result<ExecutionResult> {
        info!(command = %command, "executing local command");
        let start = std::time::Instant::now();

        #[cfg(target_os = "windows")]
        let mut cmd = Command::new("powershell");
        #[cfg(target_os = "windows")]
        cmd.arg("-Command").arg(command);

        #[cfg(not(target_os = "windows"))]
        let mut cmd = Command::new("sh");
        #[cfg(not(target_os = "windows"))]
        cmd.arg("-c").arg(command);

        cmd.current_dir(&self.working_dir)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);

        let mut child = cmd.spawn().context("failed to spawn command")?;
        let stdout = child.stdout.take().context("missing stdout")?;
        let stderr = child.stderr.take().context("missing stderr")?;

        let mut stdout_reader = BufReader::new(stdout).lines();
        let mut stderr_reader = BufReader::new(stderr).lines();

        let mut stdout_lines = Vec::new();
        let mut stderr_lines = Vec::new();

        let exit_code = timeout(self.timeout, async {
            loop {
                tokio::select! {
                    line = stdout_reader.next_line() => {
                        match line {
                            Ok(Some(l)) => {
                                debug!(stdout = %l, "command stdout");
                                stdout_lines.push(l.clone());
                                if let Some(bus) = &self.event_bus {
                                    let _ = bus.emit(Event::Log {
                                        timestamp: chrono::Utc::now(),
                                        level: "INFO".to_string(),
                                        message: l,
                                    });
                                }
                            }
                            Ok(None) => break,
                            Err(e) => {
                                error!(error = %e, "error reading stdout");
                                break;
                            }
                        }
                    }
                    line = stderr_reader.next_line() => {
                        match line {
                            Ok(Some(l)) => {
                                debug!(stderr = %l, "command stderr");
                                stderr_lines.push(l.clone());
                                if let Some(bus) = &self.event_bus {
                                    let _ = bus.emit(Event::Log {
                                        timestamp: chrono::Utc::now(),
                                        level: "WARN".to_string(),
                                        message: l,
                                    });
                                }
                            }
                            Ok(None) => {}
                            Err(e) => {
                                error!(error = %e, "error reading stderr");
                            }
                        }
                    }
                }
            }
            child.wait().await
        })
        .await;

        let (exit_code, timed_out) = match exit_code {
            Ok(Ok(status)) => (status.code(), false),
            Ok(Err(e)) => return Err(anyhow::anyhow!("command failed: {e}")),
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
            error!(command = %command, "command timed out");
        } else if result.exit_code.unwrap_or(1) != 0 {
            error!(command = %command, exit_code = ?result.exit_code, "command failed");
        } else {
            info!(command = %command, "command succeeded");
        }

        Ok(result)
    }
}
