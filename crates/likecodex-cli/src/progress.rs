//! Progress indicators for LikeCodex CLI.
//!
//! Wraps `indicatif` to provide consistent progress bars and spinners
//! for long-running operations such as engine startup, file indexing,
//! and sandbox image pulls.

use std::time::Duration;
use tracing::{debug, warn};

/// Style of progress indicator.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProgressStyle {
    /// Determinate progress bar (percentage known).
    Bar,
    /// Indeterminate spinner (no percentage).
    Spinner,
    /// Hidden / quiet (no output).
    Quiet,
}

/// A managed progress indicator that auto-cleans up on drop.
pub struct Progress {
    style: ProgressStyle,
    message: String,
    bar: Option<indicatif::ProgressBar>,
    spinner: Option<indicatif::ProgressBar>,
}

impl Progress {
    /// Create a new progress indicator with the given message and style.
    pub fn new(message: impl Into<String>, style: ProgressStyle) -> Self {
        let message = message.into();

        match style {
            ProgressStyle::Bar => {
                let bar = indicatif::ProgressBar::new(100);
                bar.set_style(
                    indicatif::ProgressStyle::default_bar()
                        .template("{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {pos:.0}% {msg}")
                        .unwrap_or_else(|_| indicatif::ProgressStyle::default_bar())
                        .progress_chars("=> "),
                );
                bar.set_message(message.clone());
                bar.enable_steady_tick(Duration::from_millis(100));
                Self {
                    style,
                    message,
                    bar: Some(bar),
                    spinner: None,
                }
            }
            ProgressStyle::Spinner => {
                let spinner = indicatif::ProgressBar::new_spinner();
                spinner.set_style(
                    indicatif::ProgressStyle::default_spinner()
                        .template("{spinner:.cyan} [{elapsed_precise}] {msg}")
                        .unwrap_or_else(|_| indicatif::ProgressStyle::default_spinner()),
                );
                spinner.set_message(message.clone());
                spinner.enable_steady_tick(Duration::from_millis(100));
                Self {
                    style,
                    message,
                    bar: None,
                    spinner: Some(spinner),
                }
            }
            ProgressStyle::Quiet => Self {
                style,
                message,
                bar: None,
                spinner: None,
            },
        }
    }

    /// Update the progress message.
    pub fn set_message(&self, msg: impl Into<String>) {
        let msg = msg.into();
        if let Some(ref bar) = self.bar {
            bar.set_message(msg);
        }
        if let Some(ref spinner) = self.spinner {
            spinner.set_message(msg);
        }
    }

    /// Set the current progress (0–100) for bar-style indicators.
    pub fn set_progress(&self, pct: u64) {
        if let Some(ref bar) = self.bar {
            bar.set_position(pct.clamp(0, 100));
        }
    }

    /// Increment the progress bar by a delta.
    pub fn inc(&self, delta: u64) {
        if let Some(ref bar) = self.bar {
            bar.inc(delta);
        }
    }

    /// Mark the progress as finished with a success message.
    pub fn finish_with_message(&self, msg: impl Into<String>) {
        let msg = msg.into();
        if let Some(ref bar) = self.bar {
            bar.finish_with_message(msg);
        }
        if let Some(ref spinner) = self.spinner {
            spinner.finish_with_message(msg);
        }
    }

    /// Mark the progress as finished cleanly.
    pub fn finish(&self) {
        if let Some(ref bar) = self.bar {
            bar.finish_and_clear();
        }
        if let Some(ref spinner) = self.spinner {
            spinner.finish_and_clear();
        }
    }

    /// Abort the progress with an error message.
    pub fn abort(&self, msg: impl Into<String>) {
        let msg = msg.into();
        warn!("progress aborted: {msg}");
        if let Some(ref bar) = self.bar {
            bar.abandon_with_message(msg);
        }
        if let Some(ref spinner) = self.spinner {
            spinner.abandon_with_message(msg);
        }
    }
}

impl Drop for Progress {
    fn drop(&mut self) {
        if let Some(ref bar) = self.bar {
            bar.finish_and_clear();
        }
        if let Some(ref spinner) = self.spinner {
            spinner.finish_and_clear();
        }
    }
}

/// Convenience functions for common progress scenarios.
pub mod tasks {
    use super::*;

    /// Show a spinner for engine startup.
    pub fn engine_startup() -> Progress {
        Progress::new("Starting engine...", ProgressStyle::Spinner)
    }

    /// Show a progress bar for file indexing.
    pub fn file_indexing(total: u64) -> Progress {
        let bar = indicatif::ProgressBar::new(total);
        bar.set_style(
            indicatif::ProgressStyle::default_bar()
                .template("{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {pos}/{len} {msg}")
                .unwrap_or_else(|_| indicatif::ProgressStyle::default_bar())
                .progress_chars("=> "),
        );
        bar.set_message("Indexing files...");
        bar.enable_steady_tick(Duration::from_millis(100));

        Progress {
            style: ProgressStyle::Bar,
            message: "Indexing files...".to_string(),
            bar: Some(bar),
            spinner: None,
        }
    }

    /// Show a spinner for Docker sandbox image pull/build.
    pub fn sandbox_image() -> Progress {
        Progress::new("Preparing sandbox image...", ProgressStyle::Spinner)
    }

    /// Show a spinner for a tool execution.
    pub fn tool_execution(name: &str) -> Progress {
        Progress::new(format!("Executing: {name}"), ProgressStyle::Spinner)
    }
}
