//! Terminal interaction helpers for permission prompts and confirmations.
#![allow(dead_code)]

use std::io::{self, Write};

use anyhow::{Context, Result};

/// User decision for an interactive permission prompt.
pub struct PermissionDecision {
    pub approved: bool,
    pub grant_scope: String,
}

/// Ask the user a yes/no question in the terminal.
pub fn confirm(question: &str, default: bool) -> Result<bool> {
    let prompt = if default {
        format!("{} [Y/n]: ", question)
    } else {
        format!("{} [y/N]: ", question)
    };
    print!("{}", prompt);
    io::stdout().flush().context("failed to flush stdout")?;

    let mut input = String::new();
    io::stdin()
        .read_line(&mut input)
        .context("failed to read input")?;
    let trimmed = input.trim().to_lowercase();

    if trimmed.is_empty() {
        return Ok(default);
    }
    Ok(trimmed.starts_with('y'))
}

/// Prompt the user to choose one of the provided options by number.
pub fn choose(question: &str, options: &[&str]) -> Result<usize> {
    println!("{}", question);
    for (i, option) in options.iter().enumerate() {
        println!("  [{}] {}", i + 1, option);
    }
    print!("Select (1-{}): ", options.len());
    io::stdout().flush().context("failed to flush stdout")?;

    let mut input = String::new();
    io::stdin()
        .read_line(&mut input)
        .context("failed to read input")?;
    let choice: usize = input.trim().parse().context("invalid selection")?;

    if choice == 0 || choice > options.len() {
        anyhow::bail!("selection out of range");
    }
    Ok(choice - 1)
}

/// Print a permission request to the terminal and return the user's decision.
pub fn request_permission(description: &str, command: Option<&str>) -> Result<bool> {
    Ok(request_permission_with_scope(description, command)?.approved)
}

/// Permission prompt with Reasonix-style grant scopes.
pub fn request_permission_with_scope(
    description: &str,
    command: Option<&str>,
) -> Result<PermissionDecision> {
    println!("Permission request:");
    println!("  {}", description);
    if let Some(cmd) = command {
        println!("  Command: {}", cmd);
    }
    let options = [
        "Allow once",
        "Allow for session",
        "Allow prefix (bash/shell)",
        "Deny",
    ];
    let idx = choose("Choose permission scope:", &options)?;
    match idx {
        0 => Ok(PermissionDecision {
            approved: true,
            grant_scope: "once".to_string(),
        }),
        1 => Ok(PermissionDecision {
            approved: true,
            grant_scope: "session".to_string(),
        }),
        2 => Ok(PermissionDecision {
            approved: true,
            grant_scope: "prefix".to_string(),
        }),
        _ => Ok(PermissionDecision {
            approved: false,
            grant_scope: "once".to_string(),
        }),
    }
}

/// Ask tool: pick one or more options from a list.
pub fn ask_select(question: &str, options: &[String], multi_select: bool) -> Result<Vec<usize>> {
    println!("{}", question);
    for (i, option) in options.iter().enumerate() {
        println!("  [{}] {}", i + 1, option);
    }
    if multi_select {
        print!("Select numbers (comma-separated, 1-{}): ", options.len());
    } else {
        print!("Select (1-{}): ", options.len());
    }
    io::stdout().flush().context("failed to flush stdout")?;
    let mut input = String::new();
    io::stdin()
        .read_line(&mut input)
        .context("failed to read input")?;
    let trimmed = input.trim();
    if multi_select {
        let mut picks = Vec::new();
        for part in trimmed.split(',') {
            let choice: usize = part.trim().parse().context("invalid selection")?;
            if choice == 0 || choice > options.len() {
                anyhow::bail!("selection out of range");
            }
            picks.push(choice - 1);
        }
        if picks.is_empty() {
            anyhow::bail!("select at least one option");
        }
        return Ok(picks);
    }
    let choice: usize = trimmed.parse().context("invalid selection")?;
    if choice == 0 || choice > options.len() {
        anyhow::bail!("selection out of range");
    }
    Ok(vec![choice - 1])
}
