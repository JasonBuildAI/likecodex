/// PTY Terminal Manager — manages shell subprocesses for terminal sessions.
///
/// Each session spawns a shell (PowerShell on Windows, bash on Unix) and
/// exposes read/write access via tokio pipes. The frontend connects via
/// WebSocket for real-time I/O, and can request resize events.

use anyhow::{Context, Result};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::{mpsc, Mutex};
use tracing::{debug, error, info};

/// A handle to a running PTY session.
pub struct PtySession {
    pub id: String,
    pub cwd: String,
    pub shell: String,
    /// Sender for writing commands to the shell's stdin.
    stdin_tx: mpsc::Sender<String>,
    /// Receiver side exposed as a stream of output lines.
    pub output_rx: mpsc::Receiver<String>,
    /// The underlying child process — kept alive for the session duration.
    _child: Option<Child>,
}

impl PtySession {
    /// Write a command (line) to the shell's stdin.
    pub async fn write_stdin(&self, line: &str) -> Result<()> {
        self.stdin_tx
            .send(format!("{}\n", line))
            .await
            .context("stdin channel closed")
    }

    /// Send a terminal resize event (rows, cols).
    /// On supported platforms, adjusts the pty window size.
    #[allow(unused_variables)]
    pub async fn resize(&self, rows: u16, cols: u16) -> Result<()> {
        // On Unix, we could send SIGWINCH. On Windows, resize is not directly
        // supported via child process handles — the frontend is responsible
        // for re-flowing output. Logged for future platform-specific impl.
        debug!(session = %self.id, rows, cols, "pty resize requested");
        Ok(())
    }
}

/// Manages all active PTY terminal sessions.
#[derive(Clone)]
pub struct PtyManager {
    sessions: Arc<Mutex<HashMap<String, PtySession>>>,
}

impl PtyManager {
    pub fn new() -> Self {
        Self {
            sessions: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// Spawn a new shell session in the given working directory.
    pub async fn create_session(&self, id: String, cwd: String) -> Result<()> {
        let shell = if cfg!(windows) {
            "powershell.exe"
        } else {
            "/bin/bash"
        };

        let mut cmd = if cfg!(windows) {
            let mut c = Command::new("powershell.exe");
            c.args(["-NoProfile", "-NoExit", "-Command", "-"]);
            c
        } else {
            let mut c = Command::new("/bin/bash");
            c.arg("--login");
            c
        };

        cmd.current_dir(&cwd)
            .env("TERM", "xterm-256color")
            .env("LANG", "en_US.UTF-8")
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped());

        let mut child = cmd.spawn().context("failed to spawn shell")?;

        let stdin = child.stdin.take().context("no stdin on child")?;
        let stdout = child.stdout.take().context("no stdout on child")?;
        let stderr = child.stderr.take().context("no stderr on child")?;

        let (stdin_tx, mut stdin_rx) = mpsc::channel::<String>(256);
        let (output_tx, output_rx) = mpsc::channel::<String>(256);

        // Task: forward stdin_rx to the shell's stdin handle
        let stdin_handle = tokio::spawn(async move {
            let mut writer = tokio::io::BufWriter::new(stdin);
            while let Some(line) = stdin_rx.recv().await {
                if let Err(e) = writer.write_all(line.as_bytes()).await {
                    error!(error = %e, "stdin write error");
                    break;
                }
                let _ = writer.flush().await;
            }
        });

        // Task: read stdout lines and forward to output_tx
        let out_tx = output_tx.clone();
        let stdout_handle = tokio::spawn(async move {
            let mut reader = BufReader::new(stdout);
            let mut line = String::new();
            loop {
                line.clear();
                match reader.read_line(&mut line).await {
                    Ok(0) => break,
                    Ok(_) => {
                        if out_tx.send(line.clone()).await.is_err() {
                            break;
                        }
                    }
                    Err(e) => {
                        error!(error = %e, "stdout read error");
                        break;
                    }
                }
            }
        });

        // Task: read stderr lines and forward to output_tx
        let err_tx = output_tx.clone();
        let stderr_handle = tokio::spawn(async move {
            let mut reader = BufReader::new(stderr);
            let mut line = String::new();
            loop {
                line.clear();
                match reader.read_line(&mut line).await {
                    Ok(0) => break,
                    Ok(_) => {
                        if err_tx.send(line.clone()).await.is_err() {
                            break;
                        }
                    }
                    Err(e) => {
                        error!(error = %e, "stderr read error");
                        break;
                    }
                }
            }
        });

        let session = PtySession {
            id: id.clone(),
            cwd,
            shell: shell.to_string(),
            stdin_tx,
            output_rx,
            _child: Some(child),
        };

        let mut sessions = self.sessions.lock().await;
        sessions.insert(id.clone(), session);

        info!(session = %id, "PTY session created");
        Ok(())
    }

    /// Get a reference to a session's sender for stdin writes.
    pub async fn get_session(&self, id: &str) -> Option<mpsc::Sender<String>> {
        let sessions = self.sessions.lock().await;
        sessions.get(id).map(|s| s.stdin_tx.clone())
    }

    /// Remove and clean up a session.
    pub async fn close_session(&self, id: &str) -> bool {
        let mut sessions = self.sessions.lock().await;
        let removed = sessions.remove(id);
        if removed.is_some() {
            info!(session = %id, "PTY session closed");
            true
        } else {
            false
        }
    }

    /// List active session IDs.
    pub async fn list_sessions(&self) -> Vec<String> {
        let sessions = self.sessions.lock().await;
        sessions.keys().cloned().collect()
    }
}
