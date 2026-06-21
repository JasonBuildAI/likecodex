//! Environment diagnostics with actionable fix hints.

use std::env;
use std::process::Command;

use anyhow::Result;
use likecodex_core::config::Config;
use reqwest::Client;
use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct DoctorCheck {
    pub name: String,
    pub status: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fix: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct DoctorReport {
    pub version: String,
    pub checks: Vec<DoctorCheck>,
    pub ok: bool,
}

pub async fn run_doctor(
    client: &Client,
    config: &Config,
    engine_url: &str,
    server_url: &str,
    web_url: &str,
    security: bool,
    json: bool,
) -> Result<()> {
    let mut checks = Vec::new();

    checks.push(DoctorCheck {
        name: "cli".into(),
        status: "ok".into(),
        message: format!("likecodex CLI {}", env!("CARGO_PKG_VERSION")),
        fix: None,
    });

    checks.push(tool_check("uv", &["--version"], "Install uv: https://docs.astral.sh/uv/"));
    checks.push(tool_check(
        "python",
        &["--version"],
        "Install Python 3.11+",
    ));
    checks.push(tool_check(
        "git",
        &["--version"],
        "Install git (optional but recommended)",
    ));

    let has_key = config.llm.api_key.is_some()
        || env::var("DEEPSEEK_API_KEY").is_ok()
        || env::var("LIKECODEX_LLM_API_KEY").is_ok();
    checks.push(if has_key {
        DoctorCheck {
            name: "api_key".into(),
            status: "ok".into(),
            message: "DeepSeek API key configured".into(),
            fix: None,
        }
    } else {
        DoctorCheck {
            name: "api_key".into(),
            status: "warn".into(),
            message: "DEEPSEEK_API_KEY not set".into(),
            fix: Some("Run `likecodex setup` or set DEEPSEEK_API_KEY".into()),
        }
    });

    checks.push(service_check(
        client,
        "engine",
        &format!("{engine_url}/health"),
        "Engine not reachable",
        Some("Run `likecodex start` or ensure Python engine is running".into()),
    )
    .await);

    checks.push(service_check(
        client,
        "server",
        &format!("{server_url}/health"),
        "Rust API server not reachable",
        Some("Run `likecodex start` to launch the API server on port 8080".into()),
    )
    .await);

    checks.push(service_check(
        client,
        "web",
        web_url,
        "Web UI not reachable",
        Some("Run `likecodex start --web` to launch the browser UI".into()),
    )
    .await);

    if config.mcp.enabled {
        if config.mcp.servers.is_empty() {
            checks.push(DoctorCheck {
                name: "mcp".into(),
                status: "warn".into(),
                message: "MCP enabled but no servers configured".into(),
                fix: Some("Add [[mcp.servers.*]] to ~/.likecodex/config.toml or .mcp.json".into()),
            });
        } else {
            for (name, server) in &config.mcp.servers {
                checks.push(DoctorCheck {
                    name: format!("mcp.{name}"),
                    status: if server.enabled { "ok".into() } else { "info".into() },
                    message: format!("MCP server `{name}` command={}", server.command),
                    fix: None,
                });
            }
        }
    }

    if security {
        match Command::new("docker")
            .args(["images", "-q", "likecodex/sandbox"])
            .output()
        {
            Ok(out) if out.status.success() && !out.stdout.is_empty() => {
                checks.push(DoctorCheck {
                    name: "sandbox".into(),
                    status: "ok".into(),
                    message: "Sandbox image likecodex/sandbox present".into(),
                    fix: None,
                });
            }
            _ => {
                checks.push(DoctorCheck {
                    name: "sandbox".into(),
                    status: "warn".into(),
                    message: "Sandbox image missing".into(),
                    fix: Some(
                        "docker build -t likecodex/sandbox:latest docker/sandbox".into(),
                    ),
                });
            }
        }
        checks.push(DoctorCheck {
            name: "approval_mode".into(),
            status: "info".into(),
            message: format!("approval mode: {}", config.approval.mode),
            fix: None,
        });
    }

    let ok = checks.iter().all(|c| c.status != "warn" && c.status != "error");
    let report = DoctorReport {
        version: env!("CARGO_PKG_VERSION").to_string(),
        checks,
        ok,
    };

    if json {
        println!("{}", serde_json::to_string_pretty(&report)?);
    } else {
        println!("LikeCodex Doctor\n");
        for check in &report.checks {
            let prefix = match check.status.as_str() {
                "ok" => "[ok]",
                "warn" => "[warn]",
                "error" => "[error]",
                _ => "[info]",
            };
            println!("{prefix} {}", check.message);
            if let Some(fix) = &check.fix {
                println!("      fix: {fix}");
            }
        }
        if report.ok {
            println!("\nAll checks passed.");
        } else {
            println!("\nSome checks need attention.");
        }
    }

    Ok(())
}

fn tool_check(name: &str, args: &[&str], fix: &str) -> DoctorCheck {
    match Command::new(name).args(args).output() {
        Ok(out) if out.status.success() => DoctorCheck {
            name: name.to_string(),
            status: "ok".into(),
            message: format!("{name} {}", String::from_utf8_lossy(&out.stdout).trim()),
            fix: None,
        },
        _ => DoctorCheck {
            name: name.to_string(),
            status: "warn".into(),
            message: format!("{name} not found"),
            fix: Some(fix.to_string()),
        },
    }
}

async fn service_check(
    client: &Client,
    name: &str,
    url: &str,
    fail_message: &str,
    fix: Option<String>,
) -> DoctorCheck {
    match client.get(url).send().await {
        Ok(resp) if resp.status().is_success() => DoctorCheck {
            name: name.to_string(),
            status: "ok".into(),
            message: format!("{name} reachable at {url}"),
            fix: None,
        },
        Ok(resp) => DoctorCheck {
            name: name.to_string(),
            status: "warn".into(),
            message: format!("{name} returned HTTP {}", resp.status()),
            fix: fix.clone(),
        },
        Err(_) => DoctorCheck {
            name: name.to_string(),
            status: "warn".into(),
            message: fail_message.to_string(),
            fix,
        },
    }
}
