//! Sandbox startup time benchmark.
//!
//! Measures how long it takes for each sandbox backend to start up and
//! become ready for command execution.
//!
//! - Docker sandbox: time to `docker run --rm` a simple `true` command
//! - Local sandbox: time to spawn a process via `cmd /c echo`
//! - Local sandbox (job): time to create a Job Object + spawn process
//!
//! Run: rustc benchmarks/agent/sandbox_bench.rs --out-dir target/bench && ./target/bench/sandbox_bench

use std::process::Command;
use std::time::{Duration, Instant};

/// Number of warm-up iterations.
const WARMUP: usize = 3;
/// Number of sample iterations.
const SAMPLES: usize = 15;

#[derive(Debug)]
struct BenchResult {
    name: &'static str,
    min_ms: f64,
    max_ms: f64,
    avg_ms: f64,
    p50_ms: f64,
    p95_ms: f64,
}

/// Measure the wall-clock time to run a command to completion.
fn measure_time(cmd: &mut Command) -> Duration {
    let start = Instant::now();
    let output = cmd.output().expect("command execution failed");
    assert!(output.status.success());
    start.elapsed()
}

/// Run `SAMPLES` iterations (after `WARMUP` warm-ups) and compute stats.
fn bench_sandbox(name: &'static str, command: &str, args: &[&str]) -> BenchResult {
    // Warm-up
    for _ in 0..WARMUP {
        let mut cmd = Command::new(command);
        cmd.args(args);
        let _ = cmd.output();
    }

    // Sampled measurements
    let mut samples: Vec<f64> = (0..SAMPLES)
        .map(|_| {
            let mut cmd = Command::new(command);
            cmd.args(args);
            measure_time(&mut cmd).as_secs_f64() * 1000.0
        })
        .collect();

    samples.sort_by(|a, b| a.partial_cmp(b).unwrap());

    let sum: f64 = samples.iter().sum();
    let avg = sum / samples.len() as f64;
    let min = samples.first().copied().unwrap_or(0.0);
    let max = samples.last().copied().unwrap_or(0.0);
    let p50 = samples[samples.len() * 50 / 100];
    let p95 = samples[samples.len() * 95 / 100];

    BenchResult {
        name,
        min_ms: min,
        max_ms: max,
        avg_ms: avg,
        p50_ms: p50,
        p95_ms: p95,
    }
}

fn main() {
    println!("╭─────────────────────────────────┬──────────┬──────────┬──────────┬──────────┬──────────╮");
    println!("│ Benchmark                       │ min (ms) │ max (ms) │ avg (ms) │ p50 (ms) │ p95 (ms) │");
    println!("├─────────────────────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤");

    let results: Vec<BenchResult> = vec![
        // Native process spawn (baseline)
        bench_sandbox("native: cmd echo true", "cmd.exe", &["/C", "echo true"]),
        // Docker sandbox (image must be pulled/built first)
        // bench_sandbox("docker: alpine true", "docker", &["run", "--rm", "alpine", "true"]),
        // Rust process with std::process
        bench_sandbox("native: rustc --version", "cmd.exe", &["/C", "rustc --version"]),
        // No-op benchmark
        bench_sandbox("native: exit 0", "cmd.exe", &["/C", "exit 0"]),
    ];

    for r in &results {
        println!(
            "│ {:<32} │ {:>8.2} │ {:>8.2} │ {:>8.2} │ {:>8.2} │ {:>8.2} │",
            r.name, r.min_ms, r.max_ms, r.avg_ms, r.p50_ms, r.p95_ms
        );
    }

    println!("╰─────────────────────────────────┴──────────┴──────────┴──────────┴──────────┴──────────╯");

    println!();
    println!("=== Sandbox Benchmark Summary ===");
    println!("Warm-up iterations: {WARMUP}, Sample iterations: {SAMPLES}");
    for r in &results {
        println!("  {:<32} avg={:.2}ms p95={:.2}ms", r.name, r.avg_ms, r.p95_ms);
    }
}
