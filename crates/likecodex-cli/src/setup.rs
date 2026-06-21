//! Interactive first-time setup wizard.

use std::io::{self, Write};
use std::path::Path;
use std::process::Command;

use anyhow::{Context, Result};
use likecodex_core::config::Config;
use reqwest::Client;

use crate::engine::{self, EngineSupervisor};

pub async fn run_setup(project_root: &Path, non_interactive: bool) -> Result<()> {
    println!("LikeCodex Setup\n");

    check_tool("uv", &["--version"], "Install uv: https://docs.astral.sh/uv/")?;
    check_tool("python", &["--version"], "Install Python 3.11+")?;
    check_tool("git", &["--version"], "Install git (optional but recommended)")?;

    let mut config = Config::load().unwrap_or_default();

    if !non_interactive {
        let has_key = config.llm.api_key.is_some()
            || std::env::var("DEEPSEEK_API_KEY").is_ok()
            || std::env::var("LIKECODEX_LLM_API_KEY").is_ok();

        if !has_key {
            print!("DeepSeek API key (Enter to skip): ");
            io::stdout().flush()?;
            let mut key = String::new();
            io::stdin().read_line(&mut key)?;
            if !key.trim().is_empty() {
                config.llm.api_key = Some(key.trim().to_string());
            }
        }

        print!("Approval mode [read-only/auto/full-access] (default auto): ");
        io::stdout().flush()?;
        let mut mode = String::new();
        io::stdin().read_line(&mut mode)?;
        let mode = mode.trim();
        if !mode.is_empty() {
            config.approval.mode = mode.to_string();
        }

        print!("Enable MCP plugins? [y/N]: ");
        io::stdout().flush()?;
        let mut mcp = String::new();
        io::stdin().read_line(&mut mcp)?;
        config.mcp.enabled = mcp.trim().eq_ignore_ascii_case("y");
    }

    config.llm.provider = "deepseek".to_string();
    if config.llm.model.is_empty() {
        config.llm.model = "deepseek-v4-flash".to_string();
    }
    if config.llm.base_url.is_none() {
        config.llm.base_url = Some("https://api.deepseek.com".to_string());
    }

    let saved = config.save_user()?;
    println!("\n[ok] Wrote config to {}", saved.display());

    if let Some(engine_root) = engine::find_engine_root(project_root) {
        println!("[info] Syncing Python dependencies in {}...", engine_root.display());
        let status = Command::new("uv")
            .args(["sync", "--all-packages"])
            .current_dir(&engine_root)
            .status()
            .context("failed to run uv sync")?;
        if !status.success() {
            println!("[warn] uv sync exited with {status}");
        }
    } else {
        println!("[warn] Engine sources not found — clone the repo or run install.ps1");
    }

    ensure_project_memory(project_root)?;

    let client = Client::new();
    let engine_url = std::env::var("LIKECODEX_ENGINE_URL")
        .unwrap_or_else(|_| "http://127.0.0.1:9090".to_string());
    apply_config_env(&config);

    match EngineSupervisor::ensure_running(&client, &engine_url, project_root).await {
        Ok(_) => println!("[ok] Engine reachable at {engine_url}"),
        Err(e) => println!("[warn] Engine not reachable: {e}"),
    }

    println!("\nNext steps:");
    println!("  likecodex doctor");
    println!("  likecodex start --web");
    println!("  likecodex code");
    Ok(())
}

fn check_tool(name: &str, args: &[&str], hint: &str) -> Result<()> {
    match Command::new(name).args(args).output() {
        Ok(out) if out.status.success() => {
            let version = String::from_utf8_lossy(&out.stdout).trim().to_string();
            println!("[ok] {name} {version}");
            Ok(())
        }
        _ => {
            println!("[warn] {name} not found — {hint}");
            Ok(())
        }
    }
}

fn ensure_project_memory(project_root: &Path) -> Result<()> {
    let memory = project_root.join("LIKECODEX.md");
    if memory.exists() {
        println!("[ok] Project memory already exists: {}", memory.display());
        return Ok(());
    }

    let template = r#"# LIKECODEX Project Memory

> Edit this file to record project-specific conventions for the agent.

## Overview

Describe what this project does.

## Commands

- Build: `...`
- Test: `...`
- Lint: `...`

## Conventions

- Language / framework notes
- Directory layout
"#;
    std::fs::write(&memory, template)?;
    println!("[ok] Created {}", memory.display());
    Ok(())
}

fn apply_config_env(config: &Config) {
    std::env::set_var("LIKECODEX_LLM_PROVIDER", &config.llm.provider);
    std::env::set_var("LIKECODEX_LLM_MODEL", &config.llm.model);
    if let Some(url) = &config.llm.base_url {
        std::env::set_var("LIKECODEX_LLM_BASE_URL", url);
    }
    if let Some(key) = &config.llm.api_key {
        std::env::set_var("LIKECODEX_LLM_API_KEY", key);
        std::env::set_var("DEEPSEEK_API_KEY", key);
    }
    std::env::set_var("LIKECODEX_APPROVAL_MODE", &config.approval.mode);
    std::env::set_var(
        "LIKECODEX_ENABLE_MCP",
        if config.mcp.enabled { "true" } else { "false" },
    );
    std::env::set_var("LIKECODEX_TOKEN_MODE", &config.agent.token_mode);
}
