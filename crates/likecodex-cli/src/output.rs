//! Output formatting for LikeCodex CLI.
//!
//! Provides structured output serialisation in multiple formats:
//! - `json`: Pretty-printed JSON
//! - `jsonl`: Newline-delimited JSON (one object per line)
//! - `text`: Human-readable plain text
//!
//! This is used by `likecodex doctor --json`, `likecodex stats`, etc.

use serde::Serialize;
use serde_json::Value;

/// Output format selector.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OutputFormat {
    /// Pretty-printed JSON.
    Json,
    /// Newline-delimited JSON.
    Jsonl,
    /// Plain text.
    Text,
}

impl OutputFormat {
    /// Parse from a CLI argument string.
    pub fn from_str(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "json" => OutputFormat::Json,
            "jsonl" => OutputFormat::Jsonl,
            "text" | _ => OutputFormat::Text,
        }
    }
}

impl std::fmt::Display for OutputFormat {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            OutputFormat::Json => write!(f, "json"),
            OutputFormat::Jsonl => write!(f, "jsonl"),
            OutputFormat::Text => write!(f, "text"),
        }
    }
}

/// Pretty-print a JSON-serialisable value according to the output format.
pub fn print_output<T: Serialize>(value: &T, format: OutputFormat) -> serde_json::Result<()> {
    match format {
        OutputFormat::Json => {
            let s = serde_json::to_string_pretty(value)?;
            println!("{s}");
        }
        OutputFormat::Jsonl => {
            let s = serde_json::to_string(value)?;
            println!("{s}");
        }
        OutputFormat::Text => {
            // For text, convert to Value first
            let val = serde_json::to_value(value)?;
            print_value_text(&val, 0);
        }
    }
    Ok(())
}

/// Write output to a string buffer instead of stdout.
pub fn format_output<T: Serialize>(
    value: &T,
    format: OutputFormat,
) -> serde_json::Result<String> {
    match format {
        OutputFormat::Json => serde_json::to_string_pretty(value),
        OutputFormat::Jsonl => serde_json::to_string(value),
        OutputFormat::Text => {
            let val = serde_json::to_value(value)?;
            let mut buf = Vec::new();
            write_value_text(&val, 0, &mut buf);
            Ok(String::from_utf8(buf).unwrap_or_default())
        }
    }
}

/// Render a JSON value as plain text.
fn print_value_text(value: &Value, indent: usize) {
    let prefix = "  ".repeat(indent);
    match value {
        Value::Null => println!("{prefix}null"),
        Value::Bool(b) => println!("{prefix}{b}"),
        Value::Number(n) => println!("{prefix}{n}"),
        Value::String(s) => println!("{prefix}{s}"),
        Value::Array(arr) => {
            for (i, v) in arr.iter().enumerate() {
                print!("{prefix}[{i}] ");
                print_value_text(v, indent);
            }
        }
        Value::Object(obj) => {
            for (key, val) in obj {
                match val {
                    Value::String(s) => println!("{prefix}{key}: {s}"),
                    Value::Number(n) => println!("{prefix}{key}: {n}"),
                    Value::Bool(b) => println!("{prefix}{key}: {b}"),
                    Value::Null => println!("{prefix}{key}: null"),
                    _ => {
                        println!("{prefix}{key}:");
                        print_value_text(val, indent + 1);
                    }
                }
            }
        }
    }
}

fn write_value_text(value: &Value, indent: usize, buf: &mut Vec<u8>) {
    use std::io::Write;
    let prefix = "  ".repeat(indent);

    match value {
        Value::Null => writeln!(buf, "{prefix}null").unwrap(),
        Value::Bool(b) => writeln!(buf, "{prefix}{b}").unwrap(),
        Value::Number(n) => writeln!(buf, "{prefix}{n}").unwrap(),
        Value::String(s) => writeln!(buf, "{prefix}{s}").unwrap(),
        Value::Array(arr) => {
            for (i, v) in arr.iter().enumerate() {
                write!(buf, "{prefix}[{i}] ").unwrap();
                write_value_text(v, indent, buf);
            }
        }
        Value::Object(obj) => {
            for (key, val) in obj {
                match val {
                    Value::String(s) => writeln!(buf, "{prefix}{key}: {s}").unwrap(),
                    Value::Number(n) => writeln!(buf, "{prefix}{key}: {n}").unwrap(),
                    Value::Bool(b) => writeln!(buf, "{prefix}{key}: {b}").unwrap(),
                    Value::Null => writeln!(buf, "{prefix}{key}: null").unwrap(),
                    _ => {
                        writeln!(buf, "{prefix}{key}:").unwrap();
                        write_value_text(val, indent + 1, buf);
                    }
                }
            }
        }
    }
}

/// Standard CLI result structure that can be serialised in any format.
#[derive(Debug, Clone, Serialize)]
pub struct CliResult {
    pub success: bool,
    pub message: Option<String>,
    pub data: Option<Value>,
    pub duration_ms: Option<u64>,
}

impl CliResult {
    pub fn ok(message: impl Into<String>) -> Self {
        Self {
            success: true,
            message: Some(message.into()),
            data: None,
            duration_ms: None,
        }
    }

    pub fn error(message: impl Into<String>) -> Self {
        Self {
            success: false,
            message: Some(message.into()),
            data: None,
            duration_ms: None,
        }
    }

    pub fn with_data(mut self, data: Value) -> Self {
        self.data = Some(data);
        self
    }

    pub fn with_duration(mut self, ms: u64) -> Self {
        self.duration_ms = Some(ms);
        self
    }
}
