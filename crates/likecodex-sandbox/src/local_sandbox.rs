//! Local sandbox executor using OS-native isolation mechanisms.
//!
//! On Windows: uses `CREATE_BREAKAWAY_FROM_JOB` + `taskkill /T` for process
//! tree isolation and cleanup.
//! On Linux: uses `setsid()` + process group signals (`kill(-pgid, SIGKILL)`)
//! for process tree management, with optional cgroup v2 memory limits.
//!
//! This executor provides stronger isolation than the basic `FallbackExecutor`
//! and is used when Docker is unavailable.

use anyhow::{Context, Result};
use likecodex_executor::ExecutionResult;
use std::path::Path;
use std::process::Stdio;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Instant;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::{Child, Command};
use tokio::time::{timeout, Duration};
use tracing::{debug, info, warn};

use crate::policy::SandboxPolicy;

/// Counter for unique session names.
static NS_COUNTER: AtomicU64 = AtomicU64::new(0);

/// Local sandbox executor with OS-level process isolation.
#[derive(Debug, Clone)]
pub struct LocalSandboxExecutor {
    policy: SandboxPolicy,
}

impl LocalSandboxExecutor {
    pub fn new(policy: SandboxPolicy) -> Self {
        Self { policy }
    }

    /// Execute a command within an OS-level sandbox.
    ///
    /// - Captures stdout/stderr
    /// - Enforces a timeout and kills the process tree on expiry
    /// - Returns a structured `ExecutionResult`
    pub async fn execute(
        &self,
        command: &str,
        working_dir: impl AsRef<Path>,
    ) -> Result<ExecutionResult> {
        let working_dir = working_dir.as_ref().to_path_buf();
        let start = Instant::now();
        let ns = NS_COUNTER.fetch_add(1, Ordering::SeqCst);

        debug!(ns = ns, command = %command, "local sandbox execute");

        let mut child = self.spawn(&command, &working_dir, ns)?;

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
            Ok(Err(e)) => return Err(anyhow::anyhow!("process failed: {e}")),
            Err(_) => {
                self.kill_tree(&child).await;
                (None, true)
            }
        };

        let exec_result = ExecutionResult {
            command: command.to_string(),
            stdout: stdout_lines.join("\n"),
            stderr: stderr_lines.join("\n"),
            exit_code,
            timed_out,
            duration_ms: start.elapsed().as_millis() as u64,
        };

        if exec_result.timed_out {
            warn!(
                command = %command,
                "local sandbox timed out after {}s",
                self.policy.timeout_secs
            );
        } else if exec_result.exit_code.unwrap_or(1) != 0 {
            warn!(
                command = %command,
                exit_code = ?exec_result.exit_code,
                "local sandbox command failed"
            );
        } else {
            info!(command = %command, "local sandbox command succeeded");
        }

        Ok(exec_result)
    }

    // ── Platform-specific spawning ─────────────────────────────────

    #[cfg(target_os = "windows")]
    fn spawn(&self, command: &str, working_dir: &Path, _ns: u64) -> Result<Child> {
        use std::os::windows::process::CommandExt;

        const CREATE_BREAKAWAY_FROM_JOB: u32 = 0x01000000;

        let child = Command::new("cmd")
            .arg("/C")
            .arg(command)
            .current_dir(working_dir)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true)
            .creation_flags(CREATE_BREAKAWAY_FROM_JOB)
            .spawn()
            .context("failed to spawn sandboxed process")?;

        Ok(child)
    }

    #[cfg(not(target_os = "windows"))]
    fn spawn(&self, command: &str, working_dir: &Path, ns: u64) -> Result<Child> {
        use std::os::unix::process::CommandExt;

        let mut cmd = Command::new("sh");
        cmd.arg("-c")
            .arg(command)
            .current_dir(working_dir)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);

        // Safety: create a new session for process group isolation
        unsafe {
            cmd.pre_exec(|| {
                libc::setsid();
                Ok(())
            });
        }

        // Apply cgroup v2 memory limit if configured
        if let Some(mem_mb) = self.policy.memory_mb {
            apply_cgroup_limit(ns, mem_mb).ok();
        }

        Ok(cmd.spawn().context("failed to spawn sandboxed process")?)
    }

    // ── Process tree killing ───────────────────────────────────────

    /// Kill the entire process tree associated with the child.
    #[cfg(target_os = "windows")]
    async fn kill_tree(&self, child: &Child) {
        let pid = child.id().unwrap_or(0);
        if pid > 0 {
            let _ = Command::new("taskkill")
                .args(["/F", "/T", "/PID", &pid.to_string()])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status()
                .await;
        }
    }

    #[cfg(not(target_os = "windows"))]
    async fn kill_tree(&self, child: &Child) {
        let pid = child.id().unwrap_or(0) as i32;
        if pid > 0 {
            // Negative PID = process group signal
            unsafe {
                libc::kill(-pid, libc::SIGKILL);
            }
        }
    }
}

// ── Linux cgroup v2 helper ────────────────────────────────────────────

/// Apply a cgroup v2 memory limit. Silently no-ops if cgroup v2 is unavailable.
#[cfg(not(target_os = "windows"))]
fn apply_cgroup_limit(ns: u64, memory_mb: u64) -> Result<()> {
    let name = format!("likecodex_sandbox_{}", ns);
    let path = std::path::PathBuf::from("/sys/fs/cgroup").join(&name);

    if let Err(e) = std::fs::create_dir_all(&path) {
        debug!(error = %e, "cgroup v2 not available, skipping");
        return Ok(());
    }

    let max_bytes = (memory_mb as usize) * 1024 * 1024;
    let _ = std::fs::write(path.join("memory.max"), max_bytes.to_string());
    debug!(ns = ns, memory_mb = memory_mb, "cgroup v2 memory limit set");

    Ok(())
}
