use serde::{Deserialize, Serialize};
use tauri::State;

use crate::process_manager::ProcessManager;

#[derive(Debug, Serialize, Deserialize)]
pub struct ServerStatus {
    pub running: bool,
    pub port: u16,
    pub uptime_seconds: u64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AppConfig {
    pub server_port: u16,
    pub engine_port: u16,
    pub auto_start: bool,
    pub theme: String,
    pub language: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct WindowState {
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
    pub maximized: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct UpdateInfo {
    pub available: bool,
    pub version: Option<String>,
    pub download_url: Option<String>,
    pub release_notes: Option<String>,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            server_port: 3040,
            engine_port: 3041,
            auto_start: true,
            theme: "dark".to_string(),
            language: "en".to_string(),
        }
    }
}

#[tauri::command]
pub fn get_server_status(pm: State<'_, ProcessManager>) -> Result<ServerStatus, String> {
    let running = pm.is_running(1) || pm.is_running(2);
    let port = if pm.is_running(1) { 3040 } else { 0 };
    Ok(ServerStatus {
        running,
        port,
        uptime_seconds: 0,
    })
}

#[tauri::command]
pub fn get_config() -> Result<AppConfig, String> {
    Ok(AppConfig::default())
}

#[tauri::command]
pub fn save_config(config: AppConfig) -> Result<(), String> {
    // TODO: persist config to file
    println!("Saving config: {config:?}");
    Ok(())
}

#[tauri::command]
pub fn check_updates() -> Result<UpdateInfo, String> {
    Ok(UpdateInfo {
        available: false,
        version: None,
        download_url: None,
        release_notes: None,
    })
}

#[tauri::command]
pub fn get_window_state() -> Result<WindowState, String> {
    Ok(WindowState {
        x: 100,
        y: 100,
        width: 1280,
        height: 800,
        maximized: false,
    })
}

#[tauri::command]
pub fn open_project(path: String, pm: State<'_, ProcessManager>) -> Result<String, String> {
    println!("Opening project: {path}");

    if !pm.is_running(1) {
        let _ = pm.spawn_server(3040);
    }

    Ok(format!("Project opened: {path}"))
}
