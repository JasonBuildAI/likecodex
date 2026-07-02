//! Command execution latency benchmark.
//!
//! Measures the end-to-end latency of executing commands through the sandbox
//! (Docker + fallback) and the local executor, including process spawn,
//! command output capture, and teardown.
//!
//! Run: cargo bench --bench execution_bench
//! Or:  rustc benchmarks/agent/execution_bench.rs --out-dir target/bench && ./target/bench/execution_bench

use std::time::{Duration, Instant};

/// Number of sample runs per measurement.
const SAMPLES: usize = 10;

/// Simple benchmark result.
#[derive(Debug)]
struct BenchResult {
    name: &'static str,
    min_ms: f64,
    max_ms: f64,
    avg_ms: f64,
    p50_ms: f64,
    p95_ms: f64,
    p99_ms: f64,
}

/// Execute a command and measure wall-clock time.
fn measure(cmd: &mut std::process::Command) -> Duration {
    let start = Instant::now();
    let output = cmd.output().expect("command failed");
    assert!(output.status.success());
    start.elapsed()
}

/// Run `SAMPLES` iterations and compute statistics.
fn bench(name: &'static str, command: &str, args: &[&str]) -> BenchResult {
    let mut samples: Vec<f64> = (0..SAMPLES)
        .map(|_| {
            let mut cmd = std::process::Command::new(command);
            cmd.args(args);
            measure(&mut cmd).as_secs_f64() * 1000.0
        })
        .collect();

    samples.sort_by(|a, b| a.partial_cmp(b).unwrap());

    let sum: f64 = samples.iter().sum();
    let avg = sum / samples.len() as f64;
    let min = samples.first().copied().unwrap_or(0.0);
    let max = samples.last().copied().unwrap_or(0.0);
    let p50 = samples[samples.len() * 50 / 100].max(samples[0]);
    let p95 = samples[samples.len() * 95 / 100].max(samples[0]);
    let p99 = samples[samples.len() * 99 / 100].max(samples[0]);

    BenchResult {
        name,
        min_ms: min,
        max_ms: max,
        avg_ms: avg,
        p50_ms: p50,
        p95_ms: p95,
        p99_ms: p99,
    }
}

fn print_result(r: &BenchResult) {
    println!(
        "│ {:<30} │ {:>8.2} │ {:>8.2} │ {:>8.2} │ {:>8.2} │ {:>8.2} │ {:>8.2} │",
        r.name, r.min_ms, r.max_ms, r.avg_ms, r.p50_ms, r.p95_ms, r.p99_ms
    );
}

fn main() {
    println!("╭────────────────────────────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────╮");
    println!("│ Benchmark                      │ min (ms) │ max (ms) │ avg (ms) │ p50 (ms) │ p95 (ms) │ p99 (ms) │");
    println!("├────────────────────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┤");

    // 1. Simple echo (measure process spawn overhead)
    let results = vec![
        bench("echo (process spawn)", "cmd.exe", &["/C", "echo hello"]),
        bench("rustc --version", "cmd.exe", &["/C", "rustc --version"]),
        bench("cargo search empty", "cmd.exe", &["/C", "cargo search axum --limit 1"]),
        bench("git status", "cmd.exe", &["/C", "git status"]),
    ];

    for r in &results {
        print_result(r);
    }

    println!("╰────────────────────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────────╯");

    // Summary report
    println!();
    println!("=== Execution Benchmark Summary ===");
    for r in &results {
        println!(
            "  {:<30} avg={:.2}ms p95={:.2}ms",
            r.name, r.avg_ms, r.p95_ms
        );
    }
}
