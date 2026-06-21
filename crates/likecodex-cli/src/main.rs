mod doctor;
mod engine;
mod interaction;
mod setup;
mod supervisor;
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
        /// Emit JSON for programmatic consumers (Web UI).
        #[arg(long)]
        json: bool,
    },
    /// Show cache hit rate and token stats.
    Stats,
    /// List or manage sessions.
    Sessions {
        #[command(subcommand)]
        action: Option<SessionAction>,
    },
    /// List checkpoints or roll back the workspace to one.
    Rewind {
        /// Checkpoint id to restore (defaults to the most recent).
        id: Option<String>,
        /// List checkpoints instead of rewinding.
        #[arg(long)]
        list: bool,
    },
    /// Start the API server.
    Serve,
    /// Start engine + API server (+ optional Web UI).
    Start {
        /// Also launch the Next.js Web UI.
        #[arg(long)]
        web: bool,
        /// Rust API server port.
        #[arg(long, default_value_t = 8080)]
        port: u16,
        /// Python engine port.
        #[arg(long, default_value_t = 9090)]
        engine_port: u16,
        /// Web UI port (with --web).
        #[arg(long, default_value_t = 3000)]
        web_port: u16,
    },
    /// Interactive first-time setup wizard.
    Setup {
        /// Non-interactive defaults only.
        #[arg(long)]
        yes: bool,
    },
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
    std::env::set_var("LIKECODEX_TOKEN_MODE", &config.agent.token_mode);
    std::env::set_var(
        "LIKECODEX_ENABLE_MCP",
        if config.mcp.enabled { "true" } else { "false" },
    );
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

async fn ensure_engine(
    cli: &Cli,
    client: &Client,
    url: &str,
) -> Result<Option<engine::EngineSupervisor>> {
    if !cli.auto_engine {
        return Ok(None);
    }
    let cwd = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let supervisor = engine::EngineSupervisor::ensure_running(client, url, &cwd).await?;
    Ok(Some(supervisor))
}

async fn respond_permission(
    client: &Client,
    url: &str,
    request_id: &str,
    approved: bool,
) -> Result<()> {
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

    let body: Value = resp
        .json()
        .await
        .context("failed to parse engine response")?;
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
            "retrying" | "tool_dispatch" | "compaction_started" | "compaction_done" | "notice"
            | "usage" => {
                handle_stream_event(client, url, item).await?;
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

async fn handle_stream_event(client: &Client, url: &str, event: &Value) -> Result<()> {
    if event.get("cache").is_some() {
        print_cache_summary(&event["cache"]);
        return Ok(());
    }
    let event_type = event["type"].as_str().unwrap_or("assistant");
    let content = event["content"].as_str().unwrap_or("");
    match event_type {
        "delta" | "assistant" => {
            if !content.is_empty() {
                print!("{content}");
                std::io::Write::flush(&mut std::io::stdout())?;
            }
        }
        "retrying" => {
            let attempt = event
                .get("metadata")
                .and_then(|v| v.get("retry_attempt"))
                .and_then(|v| v.as_i64())
                .unwrap_or(1);
            let max = event
                .get("metadata")
                .and_then(|v| v.get("retry_max"))
                .and_then(|v| v.as_i64())
                .unwrap_or(1);
            let reason = event
                .get("metadata")
                .and_then(|v| v.get("reason"))
                .and_then(|v| v.as_str())
                .unwrap_or("retry");
            println!("\n[retrying:{reason}] ({attempt}/{max})");
        }
        "tool_dispatch" => {
            let partial = event
                .get("metadata")
                .and_then(|v| v.get("partial"))
                .and_then(|v| v.as_bool())
                .unwrap_or(true);
            if !partial {
                let name = event
                    .get("metadata")
                    .and_then(|v| v.get("tool_name"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("tool");
                println!("\n[tool] {name}");
            }
        }
        "tool_result" => {}
        "plan" => println!("\n[plan] {content}"),
        "permission" => handle_permission(client, url, content).await?,
        "compaction_started" => println!("\n[compaction] compacting conversation…"),
        "compaction_done" => println!("\n[compaction] context compacted"),
        "checkpoint" => {
            if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(content) {
                let id = parsed["checkpoint_id"].as_str().unwrap_or("?");
                let label = parsed["label"].as_str().unwrap_or("write");
                let files = parsed["files"]
                    .as_array()
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|v| v.as_str())
                            .collect::<Vec<_>>()
                            .join(", ")
                    })
                    .unwrap_or_default();
                println!("\n[checkpoint] {label} → {id} ({files})");
            } else {
                println!("\n[checkpoint] {content}");
            }
        }
        "notice" => println!("\n[notice] {content}"),
        "usage" => println!("\n{content}"),
        "error" => println!("\n[error] {content}"),
        _ => {
            if !content.is_empty() {
                println!("\n[{event_type}] {content}");
            }
        }
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
                    handle_stream_event(client, url, &event).await?;
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

async fn cmd_doctor(
    client: &Client,
    config: &Config,
    engine_url: &str,
    security: bool,
    json: bool,
) -> Result<()> {
    let server_port = config.server.port;
    let server_url = format!("http://127.0.0.1:{server_port}");
    let web_url = "http://127.0.0.1:3000".to_string();
    doctor::run_doctor(
        client,
        config,
        engine_url,
        &server_url,
        &web_url,
        security,
        json,
    )
    .await
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

async fn cmd_rewind(client: &Client, url: &str, id: Option<String>, list: bool) -> Result<()> {
    if list {
        let resp = client.get(format!("{url}/checkpoints")).send().await?;
        let body: Value = resp.json().await?;
        let empty: Vec<Value> = vec![];
        let checkpoints = body["checkpoints"].as_array().unwrap_or(&empty);
        if checkpoints.is_empty() {
            println!("[info] no checkpoints recorded yet");
        }
        for cp in checkpoints {
            let cp_id = cp["id"].as_str().unwrap_or("?");
            let label = cp["label"].as_str().unwrap_or("");
            let count = cp["files"].as_array().map(|f| f.len()).unwrap_or(0);
            println!("{cp_id}  {label}  ({count} files)");
        }
        return Ok(());
    }

    let resp = client
        .post(format!("{url}/checkpoints/rewind"))
        .json(&serde_json::json!({ "checkpoint_id": id }))
        .send()
        .await
        .context("failed to reach engine /checkpoints/rewind")?;
    let body: Value = resp.json().await?;
    if body["rewound"].as_bool().unwrap_or(false) {
        let restored = body["restored"].as_array().map(|a| a.len()).unwrap_or(0);
        let removed = body["removed"].as_array().map(|a| a.len()).unwrap_or(0);
        println!(
            "[ok] rewound to {} — restored {restored}, removed {removed}",
            body["checkpoint_id"].as_str().unwrap_or("?")
        );
    } else {
        println!(
            "[warn] rewind failed: {}",
            body["reason"].as_str().unwrap_or("unknown")
        );
    }
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
            let resp = client
                .get(format!("{url}/sessions/{id}/events"))
                .send()
                .await?;
            println!(
                "{}",
                serde_json::to_string_pretty(&resp.json::<Value>().await?)?
            );
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

    if let Some(p) = &cli.prompt {
        let _supervisor = ensure_engine(&cli, &client, &engine_url).await?;
        info!(prompt = %p, engine_url = %engine_url, "running one-shot prompt");
        run_prompt(&client, &engine_url, p).await?;
        return Ok(());
    }

    match cli.command {
        Some(Commands::Setup { yes }) => {
            let cwd = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
            setup::run_setup(&cwd, yes).await
        }
        Some(Commands::Start {
            web,
            port,
            engine_port,
            web_port,
        }) => {
            let cwd = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
            let mut cfg = config;
            cfg.server.port = port;
            apply_config_env(&cfg);
            std::env::set_var(
                "LIKECODEX_ENGINE_URL",
                format!("http://127.0.0.1:{engine_port}"),
            );
            let stack = supervisor::StackSupervisor::start(
                &client,
                &cwd,
                &cfg,
                supervisor::StartOptions {
                    web,
                    server_port: port,
                    engine_port,
                    web_port,
                },
            )
            .await?;
            stack.wait_for_shutdown().await
        }
        Some(Commands::Doctor { security, json }) => {
            cmd_doctor(&client, &config, &engine_url, security, json).await
        }
        Some(Commands::Serve) => {
            let _supervisor = ensure_engine(&cli, &client, &engine_url).await?;
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
        Some(Commands::Code) | Some(Commands::Interactive) | None => {
            let _supervisor = ensure_engine(&cli, &client, &engine_url).await?;
            info!(engine_url = %engine_url, "starting TUI session");
            tui::run_tui(client, engine_url).await
        }
        Some(Commands::Run { prompt: cmd_prompt }) => {
            let _supervisor = ensure_engine(&cli, &client, &engine_url).await?;
            run_prompt(&client, &engine_url, &cmd_prompt).await?;
            Ok(())
        }
        Some(Commands::Chat { prompt }) => {
            let _supervisor = ensure_engine(&cli, &client, &engine_url).await?;
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
        Some(Commands::Stats) => {
            let _supervisor = ensure_engine(&cli, &client, &engine_url).await?;
            cmd_stats(&client, &engine_url).await
        }
        Some(Commands::Sessions { action }) => {
            let _supervisor = ensure_engine(&cli, &client, &engine_url).await?;
            cmd_sessions(&client, &engine_url, action).await
        }
        Some(Commands::Rewind { id, list }) => {
            let _supervisor = ensure_engine(&cli, &client, &engine_url).await?;
            cmd_rewind(&client, &engine_url, id, list).await
        }
    }
}
