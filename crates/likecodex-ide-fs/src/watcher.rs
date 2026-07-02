use notify::{Config, Event, RecommendedWatcher, RecursiveMode, Watcher};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tokio::sync::broadcast;
use tracing::{error, info, warn};

/// A file system change event emitted by the watcher.
#[derive(Debug, Clone)]
pub struct FileChangeEvent {
    /// The absolute path of the affected file/directory.
    pub path: PathBuf,
    /// The kind of change detected.
    pub kind: FileChangeKind,
}

/// The kind of file system change.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FileChangeKind {
    Created,
    Modified,
    Deleted,
    Renamed,
    Other,
}

/// Start watching a directory tree, forwarding notify events into a broadcast channel.
///
/// Returns the watcher handle. The watcher runs on its own thread and forwards
/// events to the broadcast sender. The handle is returned so the caller can
/// drop it to stop watching.
pub fn start_watcher(
    root: impl AsRef<Path>,
    tx: broadcast::Sender<FileChangeEvent>,
) -> anyhow::Result<RecommendedWatcher> {
    let root = root.as_ref().to_path_buf();
    let tx = Arc::new(tx);
    let root_for_watch = root.clone();

    let mut watcher = RecommendedWatcher::new(
        move |result: Result<Event, notify::Error>| {
            if let Err(e) = handle_notify_event(result, &tx, &root) {
                error!("[ide-fs::watcher] error handling event: {e:?}");
            }
        },
        Config::default(),
    )?;

    watcher.watch(&root_for_watch, RecursiveMode::Recursive)?;
    info!("[ide-fs::watcher] started watching: {}", root_for_watch.display());

    Ok(watcher)
}

fn handle_notify_event(
    result: Result<Event, notify::Error>,
    tx: &broadcast::Sender<FileChangeEvent>,
    root: &Path,
) -> anyhow::Result<()> {
    let event = result?;

    if event.paths.is_empty() {
        return Ok(());
    }

    let kind = match event.kind {
        notify::EventKind::Create(_) => FileChangeKind::Created,
        notify::EventKind::Modify(_) => FileChangeKind::Modified,
        notify::EventKind::Remove(_) => FileChangeKind::Deleted,
        _ => FileChangeKind::Other,
    };

    for path in &event.paths {
        if path.starts_with(root) {
            let change_event = FileChangeEvent {
                path: path.clone(),
                kind: kind.clone(),
            };

            if let Err(e) = tx.send(change_event) {
                warn!("[ide-fs::watcher] no receivers: {e}");
            }
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::time::Duration;
    use tokio::sync::broadcast;
    use tokio::time::sleep;

    #[tokio::test]
    async fn test_watcher_detects_creation() {
        let dir = std::env::temp_dir().join(format!("ide-fs-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();

        let (tx, mut rx) = broadcast::channel::<FileChangeEvent>(256);
        let _watcher = start_watcher(&dir, tx).unwrap();

        // Allow watcher to initialise
        sleep(Duration::from_millis(200)).await;

        let test_file = dir.join("hello.txt");
        fs::write(&test_file, b"world").unwrap();

        // Wait for event
        let received = tokio::time::timeout(Duration::from_secs(3), rx.recv()).await;

        let _ = fs::remove_dir_all(&dir);

        assert!(received.is_ok(), "should have received a file change event");
        if let Ok(event) = received {
            assert_eq!(event.path, test_file);
            assert_eq!(event.kind, FileChangeKind::Created);
        }
    }
}
