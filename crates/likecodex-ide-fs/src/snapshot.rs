use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::SystemTime;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use tracing::warn;

/// A snapshot of the file system at a point in time.
///
/// Each snapshot records the path, size, modification time, and SHA-256 hash
/// of every file under the root directory.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileSnapshot {
    /// The root directory for this snapshot.
    pub root: PathBuf,
    /// When the snapshot was taken.
    pub timestamp: DateTime<Utc>,
    /// File entries keyed by relative path.
    pub files: HashMap<PathBuf, FileEntry>,
}

/// Metadata and hash for a single file in a snapshot.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileEntry {
    /// Size in bytes.
    pub size: u64,
    /// Last modification time.
    pub modified: SystemTime,
    /// SHA-256 hex digest.
    pub sha256: String,
}

/// The result of comparing two snapshots.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SnapshotDiff {
    /// Files that exist in the new snapshot but not the old one.
    pub added: Vec<PathBuf>,
    /// Files that exist in the old snapshot but not the new one.
    pub removed: Vec<PathBuf>,
    /// Files that exist in both snapshots but have changed.
    pub modified: Vec<PathBuf>,
    /// Files unchanged between the two snapshots.
    pub unchanged: Vec<PathBuf>,
}

impl FileSnapshot {
    /// Create a new snapshot by scanning `root` recursively.
    pub fn take(root: impl Into<PathBuf>) -> Self {
        let root = root.into();
        let timestamp = Utc::now();
        let mut files = HashMap::new();

        Self::scan_dir(&root, &root, &mut files);

        Self {
            root,
            timestamp,
            files,
        }
    }

    /// Recursively scan a directory and populate `files`.
    fn scan_dir(root: &Path, dir: &Path, files: &mut HashMap<PathBuf, FileEntry>) {
        let entries = match fs::read_dir(dir) {
            Ok(e) => e,
            Err(e) => {
                warn!("[ide-fs::snapshot] cannot read dir {}: {e}", dir.display());
                return;
            }
        };

        for entry in entries.flatten() {
            let path = entry.path();
            let ft = match entry.file_type() {
                Ok(t) => t,
                Err(e) => {
                    warn!("[ide-fs::snapshot] cannot get file type {}: {e}", path.display());
                    continue;
                }
            };

            if ft.is_dir() {
                Self::scan_dir(root, &path, files);
            } else if ft.is_file() {
                let rel_path = path.strip_prefix(root).unwrap_or(&path).to_path_buf();
                if let Some(entry) = Self::file_entry(&path) {
                    files.insert(rel_path, entry);
                }
            }
        }
    }

    /// Compute a `FileEntry` for a single file.
    fn file_entry(path: &Path) -> Option<FileEntry> {
        let meta = fs::metadata(path).ok()?;
        let size = meta.len();
        let modified = meta.modified().ok()?;

        // Read file and hash
        let mut file = fs::File::open(path).ok()?;
        let mut hasher = Sha256::new();
        let mut buf = [0u8; 8192];
        loop {
            use std::io::Read;
            let n = file.read(&mut buf).ok()?;
            if n == 0 {
                break;
            }
            hasher.update(&buf[..n]);
        }
        let sha256 = format!("{:x}", hasher.finalize());

        Some(FileEntry {
            size,
            modified,
            sha256,
        })
    }

    /// Compute the diff between this snapshot and `other`.
    ///
    /// `self` is treated as the **new** state and `other` as the **old** state.
    pub fn diff(&self, other: &FileSnapshot) -> SnapshotDiff {
        let mut added = Vec::new();
        let mut removed = Vec::new();
        let mut modified = Vec::new();
        let mut unchanged = Vec::new();

        // Files in new snapshot
        for (path, entry) in &self.files {
            match other.files.get(path) {
                None => added.push(path.clone()),
                Some(old_entry) => {
                    if entry.sha256 != old_entry.sha256 {
                        modified.push(path.clone());
                    } else {
                        unchanged.push(path.clone());
                    }
                }
            }
        }

        // Files in old snapshot but not in new
        for path in other.files.keys() {
            if !self.files.contains_key(path) {
                removed.push(path.clone());
            }
        }

        SnapshotDiff {
            added,
            removed,
            modified,
            unchanged,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn test_snapshot_and_diff() {
        let dir = std::env::temp_dir().join("ide-fs-snap-test");
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();

        // Create initial files
        fs::write(dir.join("a.txt"), b"alpha").unwrap();

        let snap1 = FileSnapshot::take(&dir);

        // Modify and add
        fs::write(dir.join("a.txt"), b"beta").unwrap();
        fs::write(dir.join("b.txt"), b"bravo").unwrap();

        let snap2 = FileSnapshot::take(&dir);

        let diff = snap2.diff(&snap1);

        assert_eq!(diff.added.len(), 1, "b.txt should be added");
        assert!(diff.added.iter().any(|p| p.ends_with("b.txt")));

        assert_eq!(diff.modified.len(), 1, "a.txt should be modified");
        assert!(diff.modified.iter().any(|p| p.ends_with("a.txt")));

        // b.txt is new, so it needs to be added too, and a.txt changed
        // unchanged should be none (a changed, b is new)
        assert!(diff.removed.is_empty());

        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_file_entry() {
        let dir = std::env::temp_dir().join("ide-fs-entry-test");
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("test.txt");
        fs::write(&path, b"hello").unwrap();

        let entry = FileSnapshot::file_entry(&path).unwrap();
        assert_eq!(entry.size, 5);
        // SHA-256 of "hello"
        let expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824";
        assert_eq!(entry.sha256, expected);

        let _ = fs::remove_dir_all(&dir);
    }
}
