mod interaction;
mod tui;

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
}

#[derive(Subcommand)]
enum Commands {
    /// Start interactive TUI session.
    Interactive,
    /// Run a single prompt and exit.
    Run { prompt: String },
    /// Start the API server.
    Serve,
    /// Show current configuration.
    Config,
}

fn engine_url(cli: &Cli) -> String {
    cli.engine_url
        .clone()
        .or_else(|| std::env::var("LIKECODEX_ENGINE_URL").ok())
        .unwrap_or_else(|| "http://127.0.0.1:9090".to_string())
}

fn apply_approval_override(approval: Option<&str>) {
    if let Some(mode) = approval {
        std::env::set_var("LIKECODEX_APPROVAL_MODE", mode);
    }
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
    let approved = interaction::request_permission(
        &format!("Allow {tool}?"),
        None,
    )?;
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
            "tool_result" => {}
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

    Ok(())
}

async fn chat_stream(client: &Client, url: &str, prompt: &str) -> Result<()> {
    let resp = client
        .post(format!("{url}/chat"))
        .json(&serde_json::json!({ "prompt": prompt }))
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

    let client = Client::new();
    let engine_url = engine_url(&cli);

    if let Some(p) = &cli.prompt {
        info!(prompt = %p, engine_url = %engine_url, "running one-shot prompt");
        run_prompt(&client, &engine_url, p).await?;
        return Ok(());
    }

    match cli.command {
        Some(Commands::Interactive) | None => {
            if cli.tui {
                info!(engine_url = %engine_url, "starting TUI session");
                tui::run_tui(client, engine_url).await
            } else {
                info!(engine_url = %engine_url, "starting interactive session");
                println!("LikeCodex interactive mode. Type your task or 'exit'.");
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
                    if let Err(e) = chat_stream(&client, &engine_url, input).await {
                        eprintln!("Error: {e}");
                    }
                    println!();
                }
                Ok(())
            }
        }
        Some(Commands::Run { prompt: cmd_prompt }) => {
            info!(prompt = %cmd_prompt, engine_url = %engine_url, "running one-shot prompt");
            run_prompt(&client, &engine_url, &cmd_prompt).await?;
            Ok(())
        }
        Some(Commands::Serve) => {
            info!("starting likecodex-server");
            let status = std::process::Command::new("cargo")
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
