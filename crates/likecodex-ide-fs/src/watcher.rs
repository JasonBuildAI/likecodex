use notify::{Config, Event, RecommendedWatcher, RecursiveMode, Watcher};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tokio::sync::broadcast;
use tracing::{error, info, warn};

/// A file system change event emitted by the watcher.
#[derive(Debug, Clone)]
pub struct FileChangeEvent {
    pub path: PathBuf,
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
            let change_event = FileChangeEvent { path: path.clone(), kind: kind.clone() };
            if let Err(e) = tx.send(change_event) {
                warn!("[ide-fs::watcher] no receivers: {e}");
            }
        }
    }
    Ok(())
}
