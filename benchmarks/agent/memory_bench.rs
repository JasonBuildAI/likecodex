//! Memory usage benchmark.
//!
//! Measures the memory footprint of key LikeCodex components:
//! - Baseline process memory
//! - Configuration loading
//! - Session state (simulated conversation)
//! - Event bus with queued messages
//! - File index metadata
//!
//! Run: rustc benchmarks/agent/memory_bench.rs --out-dir target/bench && ./target/bench/memory_bench

use std::process::Command;
use std::time::Instant;

/// Approximate memory usage measurement via OS tools.
#[derive(Debug, Clone)]
struct MemorySample {
    label: &'static str,
    /// Resident Set Size in MB (approximate).
    rss_mb: f64,
    /// Virtual memory size in MB (approximate).
    virtual_mb: f64,
}

/// Get memory usage of the current process via OS-specific means.
fn get_process_memory() -> (f64, f64) {
    // Try `wmic` on Windows first
    let pid = std::process::id();

    // Method 1: wmic (Windows)
    if cfg!(target_os = "windows") {
        let output = Command::new("wmic")
            .args([
                "process",
                "where",
                &format!("ProcessId={}", pid),
                "get",
                "WorkingSetSize,PageFileUsage",
                "/format:csv",
            ])
            .output();

        if let Ok(output) = output {
            let stdout = String::from_utf8_lossy(&output.stdout);
            for line in stdout.lines().skip(1) {
                let parts: Vec<&str> = line.split(',').collect();
                if parts.len() >= 3 {
                    let ws = parts.get(1).and_then(|s| s.trim().parse::<f64>().ok()).unwrap_or(0.0);
                    let pf = parts.get(2).and_then(|s| s.trim().parse::<f64>().ok()).unwrap_or(0.0);
                    return (ws / (1024.0 * 1024.0), pf / (1024.0 * 1024.0));
                }
            }
        }
    }

    // Method 2: /proc/self/status (Linux)
    if cfg!(target_os = "linux") {
        let content = std::fs::read_to_string("/proc/self/status").ok();
        if let Some(content) = content {
            let mut rss = 0f64;
            let mut vms = 0f64;
            for line in content.lines() {
                if let Some(val) = line.strip_prefix("VmRSS:") {
                    rss = val.trim().trim_end_matches(" kB").parse().unwrap_or(0.0) / 1024.0;
                }
                if let Some(val) = line.strip_prefix("VmSize:") {
                    vms = val.trim().trim_end_matches(" kB").parse().unwrap_or(0.0) / 1024.0;
                }
            }
            return (rss, vms);
        }
    }

    (0.0, 0.0)
}

/// Measure memory under a specific workload.
fn measure<F: FnOnce()>(label: &'static str, workload: F) -> MemorySample {
    // Small GC hint before measurement
    workload();

    let (rss, virt) = get_process_memory();
    MemorySample {
        label,
        rss_mb: rss,
        virtual_mb: virt,
    }
}

/// Allocate and hold a large Vec to simulate session state.
fn simulate_session_state(size_mb: usize) -> Vec<u8> {
    let mut data = Vec::with_capacity(size_mb * 1024 * 1024);
    data.resize(size_mb * 1024 * 1024, 0x41);
    data
}

fn main() {
    println!("=== Memory Usage Benchmark ===");
    println!("PID: {}", std::process::id());
    println!();

    let mut results = Vec::new();

    // 1. Baseline (process startup)
    let _baseline = std::time::Instant::now();
    results.push(measure("1. baseline (process init)", || {
        let _ = get_process_memory();
    }));

    // 2. Allocate a moderate data structure (e.g., 10MB session)
    let _session_10mb = simulate_session_state(10);
    results.push(measure("2. after 10MB allocation", || {
        let _ = _session_10mb.len();
    }));
    drop(_session_10mb);

    // 3. Allocate 50MB
    let _session_50mb = simulate_session_state(50);
    results.push(measure("3. after 50MB allocation", || {
        let _ = _session_50mb.len();
    }));
    drop(_session_50mb);

    // 4. Build a large HashMap (simulating file index)
    let mut index = std::collections::HashMap::new();
    for i in 0..100_000 {
        index.insert(
            format!("path/to/file_{}.rs", i),
            format!("content hash for file {} (simulated index metadata)", i),
        );
    }
    results.push(measure("4. file index (100k entries)", || {
        let _ = index.len();
    }));
    drop(index);

    // 5. Build a large Vec of strings (simulating conversation history)
    let mut conversation: Vec<String> = Vec::new();
    for i in 0..10_000 {
        conversation.push(format!(
            "[message {}] This is a simulated conversation message with some content. {}",
            i,
            "x".repeat(200)
        ));
    }
    results.push(measure("5. conversation (10k messages)", || {
        let _ = conversation.len();
    }));
    drop(conversation);

    // Print results
    println!("╭─────────────────────────────────┬──────────┬──────────────╮");
    println!("│ Measurement                     │ RSS (MB) │ Virtual (MB) │");
    println!("├─────────────────────────────────┼──────────┼──────────────┤");

    for r in &results {
        println!(
            "│ {:<32} │ {:>8.2} │ {:>12.2} │",
            r.label, r.rss_mb, r.virtual_mb
        );
    }

    println!("╰─────────────────────────────────┴──────────┴──────────────╯");

    println!();
    println!("=== Memory Summary ===");
    if let (Some(first), Some(last)) = (results.first(), results.last()) {
        let delta_rss = last.rss_mb - first.rss_mb;
        let delta_virt = last.virtual_mb - first.virtual_mb;
        println!("  Baseline RSS:  {:.2} MB", first.rss_mb);
        println!("  Final RSS:     {:.2} MB (delta: {:.2} MB)", last.rss_mb, delta_rss);
        println!(
            "  Baseline Virt: {:.2} MB",
            first.virtual_mb
        );
        println!(
            "  Final Virt:    {:.2} MB (delta: {:.2} MB)",
            last.virtual_mb, delta_virt
        );
    }
}
