use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
pub struct UpdateInfo {
    pub available: bool,
    pub version: String,
    pub current_version: String,
    pub download_url: String,
    pub release_notes: String,
    pub mandatory: bool,
}

/// Check for updates using tauri_plugin_updater.
/// Returns `UpdateInfo` describing whether a new version is available.
pub async fn check_for_updates(app: &tauri::AppHandle) -> Result<UpdateInfo, String> {
    let current_version = app.package_info().version.to_string();

    // Attempt to use the updater plugin; if not registered, return no-update.
    let updater = match app.try_state::<tauri_plugin_updater::Updater>() {
        Some(u) => u,
        None => {
            return Ok(UpdateInfo {
                available: false,
                version: current_version.clone(),
                current_version,
                download_url: String::new(),
                release_notes: String::new(),
                mandatory: false,
            });
        }
    };

    let update = updater
        .check()
        .await
        .map_err(|e| format!("Update check failed: {e}"))?;

    match update {
        Some(update) => {
            let version = update.version.clone();
            let download_url = update
                .url
                .map(|u| u.to_string())
                .unwrap_or_default();
            let release_notes = update.body.unwrap_or_default();

            Ok(UpdateInfo {
                available: true,
                version,
                current_version,
                download_url,
                release_notes,
                mandatory: update.raw_json["mandatory"].as_bool().unwrap_or(false),
            })
        }
        None => Ok(UpdateInfo {
            available: false,
            version: current_version.clone(),
            current_version,
            download_url: String::new(),
            release_notes: String::new(),
            mandatory: false,
        }),
    }
}

/// Download and install the latest update.
/// `on_progress` is called with download progress (bytes_received, total_bytes).
pub async fn download_and_install<F>(
    app: &tauri::AppHandle,
    on_progress: F,
) -> Result<(), String>
where
    F: Fn(u64, u64) + Send + 'static,
{
    let updater = app
        .try_state::<tauri_plugin_updater::Updater>()
        .ok_or("Updater plugin not registered")?;

    let update = updater
        .check()
        .await
        .map_err(|e| format!("Update check failed: {e}"))?
        .ok_or("No update available")?;

    update
        .download_and_install(
            move |chunk_length, content_length| {
                on_progress(chunk_length, content_length.unwrap_or(0));
            },
            || {},
        )
        .await
        .map_err(|e| format!("Download and install failed: {e}"))?;

    Ok(())
}
