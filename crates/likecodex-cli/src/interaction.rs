//! Terminal interaction helpers for permission prompts and confirmations.
#![allow(dead_code)]

use std::io::{self, Write};

use anyhow::{Context, Result};

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
    println!("Permission request:");
    println!("  {}", description);
    if let Some(cmd) = command {
        println!("  Command: {}", cmd);
    }
    confirm("Allow this operation?", false)
}
