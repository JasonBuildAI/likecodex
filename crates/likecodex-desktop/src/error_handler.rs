use std::backtrace::Backtrace;
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
pub struct CrashReport {
    pub timestamp: u64,
    pub message: String,
    pub backtrace: String,
}

static LAST_CRASH: Mutex<Option<CrashReport>> = Mutex::new(None);

fn crash_dir() -> PathBuf {
    let mut path = dirs_next::data_dir().unwrap_or_else(|| PathBuf::from("."));
    path.push("likecodex");
    path.push("crashes");
    path
}

/// Set up a panic hook that captures crash information and persists it to disk.
pub fn setup_panic_handler() {
    let prev = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let message = if let Some(s) = info.payload().downcast_ref::<&str>() {
            s.to_string()
        } else if let Some(s) = info.payload().downcast_ref::<String>() {
            s.clone()
        } else {
            "Unknown panic".to_string()
        };

        let backtrace = Backtrace::force_capture().to_string();
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);

        let report = CrashReport {
            timestamp,
            message,
            backtrace,
        };

        // Store in memory
        if let Ok(mut last) = LAST_CRASH.lock() {
            *last = Some(report.clone());
        }

        // Persist to disk
        let dir = crash_dir();
        let _ = fs::create_dir_all(&dir);
        let filename = format!("crash_{}.json", timestamp);
        let path = dir.join(filename);
        if let Ok(json) = serde_json::to_string_pretty(&report) {
            let _ = fs::write(&path, json);
        }

        // Call the previous hook so default panic behavior still happens
        prev(info);
    }));
}

/// Retrieve the most recent crash report, if any.
pub fn get_last_crash_report() -> Option<CrashReport> {
    if let Ok(guard) = LAST_CRASH.lock() {
        guard.clone()
    } else {
        None
    }
}

/// Attempt to restore the application state after a crash.
/// This is a placeholder — real restoration logic will depend on the application.
pub async fn setup_recovery(app: &tauri::AppHandle) -> Result<(), String> {
    let last_crash = get_last_crash_report();

    if let Some(report) = last_crash {
        eprintln!(
            "LikeCodex recovered from a crash at timestamp {}: {}",
            report.timestamp, report.message
        );

        // Emit an event to the frontend so the UI can show a recovery notification
        #[cfg(desktop)]
        {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.emit(
                    "crash-recovery",
                    serde_json::json!({
                        "recovered": true,
                        "message": format!(
                            "Recovered from crash: {}. Your work has been preserved.",
                            report.message
                        ),
                        "timestamp": report.timestamp,
                    }),
                );
            }
        }
    }

    // Clear the crash report after recovery
    if let Ok(mut last) = LAST_CRASH.lock() {
        *last = None;
    }

    Ok(())
}
