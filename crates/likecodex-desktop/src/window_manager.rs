use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Mutex;
use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindowBuilder};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WindowState {
    pub label: String,
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
    pub maximized: bool,
}

pub struct WindowManager {
    windows: Mutex<HashMap<String, WindowState>>,
}

impl Default for WindowManager {
    fn default() -> Self {
        Self::new()
    }
}

impl WindowManager {
    pub fn new() -> Self {
        Self {
            windows: Mutex::new(HashMap::new()),
        }
    }

    pub fn create_main_window(&self, app: &AppHandle) -> Result<(), String> {
        let label = "main";
        if app.get_webview_window(label).is_some() {
            return Ok(());
        }

        let state = self
            .restore_window_state(label)
            .unwrap_or(WindowState {
                label: label.to_string(),
                x: 100,
                y: 100,
                width: 1280,
                height: 800,
                maximized: false,
            });

        let window = WebviewWindowBuilder::new(app, label, WebviewUrl::App("index.html".into()))
            .inner_size(state.width as f64, state.height as f64)
            .position(state.x as f64, state.y as f64)
            .build()
            .map_err(|e| format!("Failed to create main window: {e}"))?;

        if state.maximized {
            let _ = window.maximize();
        }

        let mut windows = self.windows.lock().unwrap_or_else(|e| e.into_inner());
        windows.insert(label.to_string(), state);
        Ok(())
    }

    pub fn create_settings_window(&self, app: &AppHandle) -> Result<(), String> {
        let label = "settings";
        if app.get_webview_window(label).is_some() {
            return Ok(());
        }

        let _window = WebviewWindowBuilder::new(app, label, WebviewUrl::App("settings.html".into()))
            .title("LikeCodex Settings")
            .inner_size(600.0, 500.0)
            .resizable(true)
            .decorations(true)
            .center()
            .build()
            .map_err(|e| format!("Failed to create settings window: {e}"))?;

        Ok(())
    }

    pub fn create_terminal_window(&self, app: &AppHandle) -> Result<(), String> {
        let label = "terminal";
        if app.get_webview_window(label).is_some() {
            return Ok(());
        }

        let _window = WebviewWindowBuilder::new(
            app,
            label,
            WebviewUrl::App("terminal.html".into()),
        )
        .title("LikeCodex Terminal")
        .inner_size(800.0, 400.0)
        .resizable(true)
        .decorations(true)
        .build()
        .map_err(|e| format!("Failed to create terminal window: {e}"))?;

        Ok(())
    }

    pub fn close_window(&self, app: &AppHandle, label: &str) -> Result<(), String> {
        if let Some(window) = app.get_webview_window(label) {
            if let Ok(pos) = window.outer_position() {
                if let Ok(size) = window.inner_size() {
                    let maximized = window.is_maximizable().unwrap_or(false);
                    let state = WindowState {
                        label: label.to_string(),
                        x: pos.x,
                        y: pos.y,
                        width: size.width,
                        height: size.height,
                        maximized,
                    };
                    self.save_window_state(&state);
                }
            }
            window
                .close()
                .map_err(|e| format!("Failed to close window: {e}"))
        } else {
            Ok(())
        }
    }

    pub fn save_window_state(&self, state: &WindowState) {
        let mut windows = self.windows.lock().unwrap_or_else(|e| e.into_inner());
        windows.insert(state.label.clone(), state.clone());
        // TODO: persist to disk
    }

    pub fn restore_window_state(&self, label: &str) -> Option<WindowState> {
        let windows = self.windows.lock().unwrap_or_else(|e| e.into_inner());
        windows.get(label).cloned()
    }
}
