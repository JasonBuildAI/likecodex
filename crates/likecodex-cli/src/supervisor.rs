//! Stack supervisor — engine, Rust server, and optional Web UI.

use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::time::Duration;

use anyhow::{Context, Result, bail};
use likecodex_core::config::Config;
use reqwest::Client;
use tokio::signal;
use tokio::time::sleep;

use crate::engine::{self, EngineSupervisor};

pub struct StackSupervisor {
    engine: EngineSupervisor,
    server: Option<Child>,
    web: Option<Child>,
}

pub struct StartOptions {
    pub web: bool,
    pub server_port: u16,
    pub engine_port: u16,
    pub web_port: u16,
}

impl StackSupervisor {
    pub async fn start(
        client: &Client,
        project_root: &Path,
        config: &Config,
        opts: StartOptions,
    ) -> Result<Self> {
        let engine_url = format!("http://127.0.0.1:{}", opts.engine_port);
        let server_url = format!("http://127.0.0.1:{}", opts.server_port);

        let engine = EngineSupervisor::ensure_running(client, &engine_url, project_root).await?;

        let server = if server_health_ok(client, &server_url).await {
            None
        } else {
            Some(spawn_server(project_root, &engine_url, opts.server_port, config)?)
        };

        for _ in 0..30 {
            if server_health_ok(client, &server_url).await {
                break;
            }
            sleep(Duration::from_millis(500)).await;
        }
        if !server_health_ok(client, &server_url).await {
            bail!("Rust API server failed to start at {server_url}");
        }

        let web = if opts.web {
            let child = spawn_web(project_root, opts.web_port)?;
            Some(child)
        } else {
            None
        };

        println!();
        println!("LikeCodex is running:");
        println!("  API:    {server_url}");
        println!("  Engine: {engine_url}");
        if opts.web {
            println!("  Web:    http://127.0.0.1:{}", opts.web_port);
        }
        println!();
        println!("Press Ctrl+C to stop.");

        Ok(Self {
            engine,
            server,
            web,
        })
    }

    pub async fn wait_for_shutdown(self) -> Result<()> {
        signal::ctrl_c().await.context("failed to listen for Ctrl+C")?;
        drop(self);
        Ok(())
    }
}

impl Drop for StackSupervisor {
    fn drop(&mut self) {
        if let Some(mut web) = self.web.take() {
            let _ = web.kill();
        }
        if let Some(mut server) = self.server.take() {
            let _ = server.kill();
        }
    }
}

async fn server_health_ok(client: &Client, url: &str) -> bool {
    client
        .get(format!("{url}/health"))
        .timeout(Duration::from_secs(2))
        .send()
        .await
        .map(|r| r.status().is_success())
        .unwrap_or(false)
}

fn spawn_server(
    project_root: &Path,
    engine_url: &str,
    port: u16,
    config: &Config,
) -> Result<Child> {
    let binary = resolve_server_binary(project_root)?;
    let mut cmd = Command::new(&binary);
    cmd.env("LIKECODEX_ENGINE_URL", engine_url)
        .env("LIKECODEX_SERVER_PORT", port.to_string())
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    if let Some(token) = &config.server.api_token {
        cmd.env("LIKECODEX_API_TOKEN", token);
    }
    engine::propagate_engine_env(&mut cmd);

    cmd.spawn()
        .with_context(|| format!("failed to spawn server binary at {}", binary.display()))
}

fn resolve_server_binary(project_root: &Path) -> Result<PathBuf> {
    if let Ok(path) = std::env::var("LIKECODEX_SERVER_BIN") {
        let p = PathBuf::from(path);
        if p.exists() {
            return Ok(p);
        }
    }

    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            for name in server_binary_names() {
                let candidate = dir.join(name);
                if candidate.exists() {
                    return Ok(candidate);
                }
            }
        }
    }

    let repo = engine::find_repo_root(project_root);
    for profile in ["release", "debug"] {
        for name in server_binary_names() {
            let candidate = repo.join("target").join(profile).join(name);
            if candidate.exists() {
                return Ok(candidate);
            }
        }
    }

    bail!(
        "likecodex-server binary not found. Build with: cargo build -p likecodex-server"
    )
}

fn server_binary_names() -> [&'static str; 2] {
    if cfg!(windows) {
        ["likecodex-server.exe", "likecodex-server"]
    } else {
        ["likecodex-server", "likecodex-server.exe"]
    }
}

fn spawn_web(project_root: &Path, port: u16) -> Result<Child> {
    let repo = engine::find_repo_root(project_root);
    let web_dir = repo.join("web");
    if !web_dir.join("package.json").exists() {
        bail!("Web UI not found at {}", web_dir.display());
    }

    let npm = if cfg!(windows) { "npm.cmd" } else { "npm" };
    let production = web_dir.join(".next").exists();
    let mut cmd = Command::new(npm);
    if production {
        cmd.args(["run", "start"]);
    } else {
        cmd.args(["run", "dev"]);
    }
    cmd.current_dir(&web_dir)
        .env("PORT", port.to_string())
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    cmd.spawn()
        .with_context(|| format!("failed to spawn Web UI in {}", web_dir.display()))
}
