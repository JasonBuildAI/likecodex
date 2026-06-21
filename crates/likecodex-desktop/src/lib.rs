#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;

static SUPERVISOR: Mutex<Option<Child>> = Mutex::new(None);

fn spawn_likecodex_stack() {
    let mut guard = SUPERVISOR.lock().expect("supervisor lock");
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
        .expect("error while running LikeCodex desktop");
}
