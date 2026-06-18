mod engine;
mod interaction;
mod tui;

use std::env;
use std::path::PathBuf;
use std::process::Command;

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use futures::StreamExt;
use likecodex_core::config::Config;
use reqwest::Client;
use serde_json::Value;
use tracing::{info, warn};

#[derive(Parser)]
#[command(name = "likecodex")]
#[command(about = "A production-grade Codex-like coding agent")]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,

    /// Prompt to execute in one-shot mode.
    prompt: Option<String>,

    /// Path to config file.
    #[arg(short, long)]
    config: Option<String>,

    /// Approval mode override.
    #[arg(short, long)]
    approval: Option<String>,

    /// URL of the Python engine bridge.
    #[arg(long, env = "LIKECODEX_ENGINE_URL")]
    engine_url: Option<String>,

    /// Start the interactive TUI instead of the plain REPL.
    #[arg(long)]
    tui: bool,

    /// Auto-start the Python engine if not running.
    #[arg(long, default_value_t = true)]
    auto_engine: bool,
}

#[derive(Subcommand)]
enum Commands {
    /// Default TUI session (alias: code).
    Code,
    /// Start interactive TUI session.
    Interactive,
    /// Run a single prompt and exit.
    Run { prompt: String },
    /// Chat without tools (streaming).
    Chat { prompt: Option<String> },
    /// Check environment and connectivity.
    Doctor {
        /// Include sandbox/security checks.
        #[arg(long)]
        security: bool,
    },
    /// Show cache hit rate and token stats.
    Stats,
    /// List or manage sessions.
    Sessions {
        #[command(subcommand)]
        action: Option<SessionAction>,
    },
    /// Start the API server.
    Serve,
    /// Show current configuration.
    Config,
}

#[derive(Subcommand)]
enum SessionAction {
    List,
    Events { id: String },
}

fn engine_url(cli: &Cli) -> String {
    cli.engine_url
        .clone()
        .or_else(|| std::env::var("LIKECODEX_ENGINE_URL").ok())
        .unwrap_or_else(|| "http://127.0.0.1:9090".to_string())
}

fn apply_config_env(config: &Config) {
    std::env::set_var("LIKECODEX_LLM_PROVIDER", &config.llm.provider);
    std::env::set_var("LIKECODEX_LLM_MODEL", &config.llm.model);
    if let Some(url) = &config.llm.base_url {
        std::env::set_var("LIKECODEX_LLM_BASE_URL", url);
    }
    if let Some(key) = &config.llm.api_key {
        std::env::set_var("LIKECODEX_LLM_API_KEY", key);
    }
    std::env::set_var("LIKECODEX_APPROVAL_MODE", &config.approval.mode);
    if config.agent.enable_planner {
        std::env::set_var("LIKECODEX_ENABLE_PLANNER", "true");
    }
    if let Some(model) = &config.agent.planner_model {
        std::env::set_var("LIKECODEX_PLANNER_MODEL", model);
    }
    std::env::set_var(
        "LIKECODEX_COMPACT_RATIO",
        format!("{}", config.agent.compact_ratio),
    );
}

fn apply_approval_override(approval: Option<&str>) {
    if let Some(mode) = approval {
        std::env::set_var("LIKECODEX_APPROVAL_MODE", mode);
    }
}

async fn ensure_engine(cli: &Cli, client: &Client, url: &str) -> Result<Option<engine::EngineSupervisor>> {
    if !cli.auto_engine {
        return Ok(None);
    }
    let cwd = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let supervisor = engine::EngineSupervisor::ensure_running(client, url, &cwd).await?;
    Ok(Some(supervisor))
}

async fn respond_permission(client: &Client, url: &str, request_id: &str, approved: bool) -> Result<()> {
    let resp = client
        .post(format!("{url}/permissions/{request_id}/respond"))
        .json(&serde_json::json!({ "approved": approved }))
        .send()
        .await?;
    if !resp.status().is_success() {
        anyhow::bail!("permission response failed");
    }
    Ok(())
}

async fn handle_permission(client: &Client, url: &str, content: &str) -> Result<()> {
    let parsed: Value = serde_json::from_str(content).unwrap_or(Value::String(content.to_string()));
    let request_id = parsed["request_id"].as_str().unwrap_or("");
    let tool = parsed["tool"].as_str().unwrap_or("tool");
    if request_id.is_empty() {
        println!("[permission] {content}");
        return Ok(());
    }
    let approved = interaction::request_permission(&format!("Allow {tool}?"), None)?;
    respond_permission(client, url, request_id, approved).await?;
    Ok(())
}

async fn run_prompt(client: &Client, url: &str, prompt: &str) -> Result<()> {
    let resp = client
        .post(format!("{url}/run"))
        .json(&serde_json::json!({ "prompt": prompt }))
        .send()
        .await
        .context("failed to connect to LikeCodex engine")?;

    if !resp.status().is_success() {
        let text = resp.text().await.unwrap_or_default();
        anyhow::bail!("engine error: {text}");
    }

    let body: Value = resp.json().await.context("failed to parse engine response")?;
    let outputs = body["outputs"].as_array().cloned().unwrap_or_default();

    for item in outputs {
        let event_type = item["type"].as_str().unwrap_or("assistant");
        let content = item["content"].as_str().unwrap_or("");
        match event_type {
            "tool_result" => {
                if let Ok(parsed) = serde_json::from_str::<Value>(content) {
                    if let Some(diff) = parsed["diff"].as_str() {
                        if !diff.is_empty() {
                            println!("--- diff ---\n{diff}");
                        }
                    }
                }
            }
            "plan" => println!("[plan] {content}"),
            "permission" => handle_permission(client, url, content).await?,
            _ => {
                if !content.is_empty() {
                    println!("{content}");
                }
            }
        }
        if let Some(tcs) = item["tool_calls"].as_array() {
            for tc in tcs {
                let name = tc["name"].as_str().unwrap_or("?");
                println!("[tool] {name}");
            }
        }
    }

    if let Some(cache) = body.get("cache") {
        print_cache_summary(cache);
    }

    Ok(())
}

async fn chat_stream(client: &Client, url: &str, prompt: &str, no_tools: bool) -> Result<()> {
    let resp = client
        .post(format!("{url}/chat"))
        .json(&serde_json::json!({
            "prompt": prompt,
            "no_tools": no_tools,
        }))
        .send()
        .await
        .context("failed to connect to LikeCodex engine")?;

    if !resp.status().is_success() {
        let text = resp.text().await.unwrap_or_default();
        anyhow::bail!("engine error: {text}");
    }

    let mut stream = resp.bytes_stream();
    while let Some(chunk) = stream.next().await {
        let chunk = chunk.context("error reading stream")?;
        let text = String::from_utf8_lossy(&chunk);
        for line in text.lines() {
            let line = line.trim();
            if let Some(data) = line.strip_prefix("data: ") {
                if data == "[DONE]" {
                    return Ok(());
                }
                if let Ok(event) = serde_json::from_str::<Value>(data) {
                    if event.get("cache").is_some() {
                        print_cache_summary(&event["cache"]);
                        continue;
                    }
                    let event_type = event["type"].as_str().unwrap_or("assistant");
                    let content = event["content"].as_str().unwrap_or("");
                    match event_type {
                        "tool_result" => {}
                        "plan" => println!("[plan] {content}"),
                        "permission" => handle_permission(client, url, content).await?,
                        _ => {
                            if !content.is_empty() {
                                print!("{content}");
                                std::io::Write::flush(&mut std::io::stdout())?;
                            }
                        }
                    }
                }
            }
        }
    }

    Ok(())
}

fn print_cache_summary(cache: &Value) {
    let hit_rate = cache["hit_rate"].as_f64().unwrap_or(0.0) * 100.0;
    let hits = cache["total_hit_tokens"].as_u64().unwrap_or(0);
    let misses = cache["total_miss_tokens"].as_u64().unwrap_or(0);
    println!(
        "\n[cache] hit {:.1}% | hit_tokens={hits} miss_tokens={misses}",
        hit_rate
    );
}

async fn cmd_doctor(client: &Client, url: &str, security: bool) -> Result<()> {
    println!("LikeCodex Doctor\n");

    println!("[ok] likecodex CLI {}", env!("CARGO_PKG_VERSION"));

    match Command::new("uv").arg("--version").output() {
        Ok(out) if out.status.success() => {
            println!("[ok] uv {}", String::from_utf8_lossy(&out.stdout).trim());
        }
        _ => println!("[warn] uv not found — install from https://docs.astral.sh/uv/"),
    }

    match Command::new("python").arg("--version").output() {
        Ok(out) if out.status.success() => {
            println!("[ok] python {}", String::from_utf8_lossy(&out.stdout).trim());
        }
        _ => println!("[warn] python not found in PATH"),
    }

    if std::env::var("DEEPSEEK_API_KEY").is_ok() || std::env::var("LIKECODEX_LLM_API_KEY").is_ok() {
        println!("[ok] DeepSeek API key configured");
    } else {
        println!("[warn] DEEPSEEK_API_KEY not set");
    }

    match client.get(format!("{url}/health")).send().await {
        Ok(resp) if resp.status().is_success() => println!("[ok] engine reachable at {url}"),
        Ok(resp) => println!("[warn] engine at {url} returned {}", resp.status()),
        Err(e) => println!("[warn] engine not reachable at {url}: {e}"),
    }

    if security {
        match Command::new("docker").args(["images", "-q", "likecodex/sandbox"]).output() {
            Ok(out) if out.status.success() && !out.stdout.is_empty() => {
                println!("[ok] sandbox image likecodex/sandbox present");
            }
            _ => println!(
                "[warn] sandbox image missing — run: docker build -t likecodex/sandbox:latest docker/sandbox"
            ),
        }
        println!("[info] approval mode: {}", env::var("LIKECODEX_APPROVAL_MODE").unwrap_or_else(|_| "auto".into()));
    }

    Ok(())
}

async fn cmd_stats(client: &Client, url: &str) -> Result<()> {
    let resp = client
        .get(format!("{url}/metrics"))
        .send()
        .await
        .context("failed to reach engine /metrics")?;
    let body: Value = resp.json().await?;
    println!("{}", serde_json::to_string_pretty(&body)?);
    Ok(())
}

async fn cmd_sessions(client: &Client, url: &str, action: Option<SessionAction>) -> Result<()> {
    match action.unwrap_or(SessionAction::List) {
        SessionAction::List => {
            let resp = client.get(format!("{url}/sessions")).send().await?;
            let body: Value = resp.json().await?;
            let empty: Vec<Value> = vec![];
            let sessions = body["sessions"].as_array().unwrap_or(&empty);
            for session in sessions {
                let id = session["id"].as_str().unwrap_or("?");
                let meta = &session["metadata"];
                let wd = meta["working_dir"].as_str().unwrap_or("");
                println!("{id}  {wd}");
            }
        }
        SessionAction::Events { id } => {
            let resp = client.get(format!("{url}/sessions/{id}/events")).send().await?;
            println!("{}", serde_json::to_string_pretty(&resp.json::<Value>().await?)?);
        }
    }
    Ok(())
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt::init();
    let cli = Cli::parse();
    apply_approval_override(cli.approval.as_deref());

    let config = if let Some(path) = &cli.config {
        Config::load_from(path)?
    } else {
        Config::load().unwrap_or_else(|e| {
            warn!(error = %e, "failed to load config, using defaults");
            Config::default()
        })
    };
    apply_config_env(&config);

    let client = Client::new();
    let engine_url = engine_url(&cli);
    let _supervisor = ensure_engine(&cli, &client, &engine_url).await?;

    if let Some(p) = &cli.prompt {
        info!(prompt = %p, engine_url = %engine_url, "running one-shot prompt");
        run_prompt(&client, &engine_url, p).await?;
        return Ok(());
    }

    match cli.command {
        Some(Commands::Code) | Some(Commands::Interactive) | None => {
            info!(engine_url = %engine_url, "starting TUI session");
            tui::run_tui(client, engine_url).await
        }
        Some(Commands::Run { prompt: cmd_prompt }) => {
            run_prompt(&client, &engine_url, &cmd_prompt).await?;
            Ok(())
        }
        Some(Commands::Chat { prompt }) => {
            if let Some(p) = prompt {
                chat_stream(&client, &engine_url, &p, true).await?;
            } else {
                println!("LikeCodex chat (no tools). Type 'exit' to quit.");
                loop {
                    print!("> ");
                    std::io::Write::flush(&mut std::io::stdout())?;
                    let mut input = String::new();
                    std::io::stdin().read_line(&mut input)?;
                    let input = input.trim();
                    if input.eq_ignore_ascii_case("exit") {
                        break;
                    }
                    if input.is_empty() {
                        continue;
                    }
                    chat_stream(&client, &engine_url, input, true).await?;
                    println!();
                }
            }
            Ok(())
        }
        Some(Commands::Doctor { security }) => cmd_doctor(&client, &engine_url, security).await,
        Some(Commands::Stats) => cmd_stats(&client, &engine_url).await,
        Some(Commands::Sessions { action }) => cmd_sessions(&client, &engine_url, action).await,
        Some(Commands::Serve) => {
            let status = Command::new("cargo")
                .args(["run", "-p", "likecodex-server"])
                .status()
                .context("failed to spawn likecodex-server")?;
            if !status.success() {
                anyhow::bail!("likecodex-server exited with {status}");
            }
            Ok(())
        }
        Some(Commands::Config) => {
            println!("{}", serde_json::to_string_pretty(&config.redacted())?);
            Ok(())
        }
    }
}
