//! Engine subprocess supervisor — starts the Python bridge when needed.

use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::time::Duration;

use anyhow::{Context, Result};
use reqwest::Client;
use tokio::time::sleep;

pub struct EngineSupervisor {
    child: Option<Child>,
}

impl EngineSupervisor {
    /// Ensure the engine at `url` responds to `/health`, spawning it if necessary.
    pub async fn ensure_running(client: &Client, url: &str, project_root: &Path) -> Result<Self> {
        if health_ok(client, url).await {
            return Ok(Self { child: None });
        }

        let host_port = parse_host_port(url);
        let mut child = spawn_engine(project_root, &host_port)?;
        for _ in 0..30 {
            sleep(Duration::from_millis(500)).await;
            if health_ok(client, url).await {
                return Ok(Self { child: Some(child) });
            }
        }
        let _ = child.kill();
        anyhow::bail!("engine failed to start at {url}")
    }
}

impl Drop for EngineSupervisor {
    fn drop(&mut self) {
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
        }
    }
}

async fn health_ok(client: &Client, url: &str) -> bool {
    client
        .get(format!("{url}/health"))
        .timeout(Duration::from_secs(2))
        .send()
        .await
        .map(|r| r.status().is_success())
        .unwrap_or(false)
}

fn parse_host_port(url: &str) -> (String, String) {
    let trimmed = url.trim_end_matches('/');
    let rest = trimmed
        .strip_prefix("http://")
        .or_else(|| trimmed.strip_prefix("https://"));
    match rest {
        Some(host_port) if host_port.contains(':') => {
            let mut parts = host_port.splitn(2, ':');
            (
                parts.next().unwrap_or("127.0.0.1").to_string(),
                parts.next().unwrap_or("9090").to_string(),
            )
        }
        Some(host) => (host.to_string(), "9090".to_string()),
        None => ("127.0.0.1".to_string(), "9090".to_string()),
    }
}

fn spawn_engine(project_root: &Path, host_port: &(String, String)) -> Result<Child> {
    let (host, port) = host_port;
    let cwd = find_engine_root(project_root);

    let uv = which_uv();
    let mut cmd = Command::new(&uv);
    cmd.args(["run", "python", "-m", "likecodex_engine.server"])
        .current_dir(&cwd)
        .env("LIKECODEX_ENGINE_HOST", host)
        .env("LIKECODEX_ENGINE_PORT", port)
        .env(
            "LIKECODEX_WORKING_DIR",
            project_root.to_string_lossy().to_string(),
        )
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    if let Ok(key) = std::env::var("DEEPSEEK_API_KEY") {
        cmd.env("DEEPSEEK_API_KEY", key);
    }
    if let Ok(key) = std::env::var("LIKECODEX_LLM_API_KEY") {
        cmd.env("LIKECODEX_LLM_API_KEY", key);
    }

    cmd.spawn()
        .with_context(|| format!("failed to spawn engine via {uv}"))
}

fn which_uv() -> String {
    std::env::var("LIKECODEX_UV").unwrap_or_else(|_| "uv".to_string())
}

fn find_engine_root(start: &Path) -> PathBuf {
    let mut dir = start.to_path_buf();
    for _ in 0..8 {
        if dir.join("packages/likecodex-engine").exists() {
            return dir;
        }
        if !dir.pop() {
            break;
        }
    }
    start.to_path_buf()
}
