#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod error_handler;
mod process_manager;
mod updater;
mod window_manager;

use process_manager::ProcessManager;
use window_manager::WindowManager;

use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Set up panic handler before anything else
    error_handler::setup_panic_handler();

    tauri::Builder::default()
        .manage(ProcessManager::new())
        .manage(WindowManager::new())
        .invoke_handler(tauri::generate_handler![
            commands::get_server_status,
            commands::get_config,
            commands::save_config,
            commands::check_updates,
            commands::get_window_state,
            commands::open_project,
        ])
        .setup(|app| {
            // Spawn the likecodex server process
            let pm: tauri::State<'_, ProcessManager> = app.state();
            if let Err(e) = pm.spawn_server(3040) {
                eprintln!("Failed to spawn server: {e}");
            }

            // Auto-spawn engine
            if let Err(e) = pm.spawn_engine(3041) {
                eprintln!("Failed to spawn engine: {e}");
            }

            // Create the main window via WindowManager
            let wm: tauri::State<'_, WindowManager> = app.state();
            if let Err(e) = wm.create_main_window(app.handle()) {
                eprintln!("Failed to create main window: {e}");
            }

            // Run crash recovery
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if let Err(e) = error_handler::setup_recovery(&handle).await {
                    eprintln!("Crash recovery failed: {e}");
                }
            });

            // Inject keyboard shortcuts into the main window
            #[cfg(desktop)]
            {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.eval(
                        "document.addEventListener('keydown', (e) => {\
                         if (e.shiftKey && e.key === 'Tab') { e.preventDefault(); window.dispatchEvent(new CustomEvent('likecodex-plan')); }\
                         if (e.ctrlKey && e.key === 'y') { e.preventDefault(); window.dispatchEvent(new CustomEvent('likecodex-yolo')); }\
                         });",
                    );
                }
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                // Kill all child processes on window destroy
                if let Some(pm) = window.try_state::<ProcessManager>() {
                    pm.kill_all();
                }
            }
        })
        .run(tauri::generate_context!())
        .unwrap_or_else(|e| {
            // Cleanup child processes before exiting
            eprintln!("LikeCodex desktop error: {e}");
        });
}
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;

static SUPERVISOR: Mutex<Option<Child>> = Mutex::new(None);

fn spawn_likecodex_stack() {
    let mut guard = SUPERVISOR.lock().unwrap_or_else(|e| e.into_inner());
    if guard.is_some() {
        return;
    }
    if let Ok(child) = Command::new("likecodex")
        .args(["start", "--no-browser"])
        .spawn()
    {
        *guard = Some(child);
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    spawn_likecodex_stack();

    tauri::Builder::default()
        .setup(|app| {
            #[cfg(desktop)]
            {
                use tauri::Manager;
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.eval(
                        "document.addEventListener('keydown', (e) => {\
                         if (e.shiftKey && e.key === 'Tab') { e.preventDefault(); window.dispatchEvent(new CustomEvent('likecodex-plan')); }\
                         if (e.ctrlKey && e.key === 'y') { e.preventDefault(); window.dispatchEvent(new CustomEvent('likecodex-yolo')); }\
                         });",
                    );
                }
            }
            Ok(())
        })
        .on_window_event(|_window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Ok(mut guard) = SUPERVISOR.lock() {
                    if let Some(mut child) = guard.take() {
                        let _ = child.kill();
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .unwrap_or_else(|e| {
            // Cleanup child process before exiting
            if let Ok(mut guard) = SUPERVISOR.lock() {
                if let Some(mut child) = guard.take() {
                    let _ = child.kill();
                }
            }
            eprintln!("LikeCodex desktop error: {e}");
        });
}
