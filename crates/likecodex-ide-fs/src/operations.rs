use std::path::{Path, PathBuf};
use tokio::fs;
use tracing::{error, info};

/// Errors that can occur during file operations.
#[derive(Debug, thiserror::Error)]
pub enum OperationError {
    #[error("path traversal detected: {path}")]
    PathTraversal { path: PathBuf },

    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    #[error("path is not within allowed root: {path}")]
    OutsideRoot { path: PathBuf },
}

/// A safe file operations layer that prevents path traversal attacks.
///
/// All operations check that the provided paths are within the configured
/// root directory. Symbolic links are resolved to their canonical form.
#[derive(Debug, Clone)]
pub struct FileOperations {
    root: PathBuf,
}

impl FileOperations {
    /// Create a new operations guard rooted at `root`.
    ///
    /// The `root` is canonicalized so that all path checks are consistent.
    pub fn new(root: impl AsRef<Path>) -> Result<Self, OperationError> {
        let root = root.as_ref().canonicalize()?;
        Ok(Self { root })
    }

    /// Return the root directory.
    pub fn root(&self) -> &Path {
        &self.root
    }

    // ── Path validation ──────────────────────────────────────────────

    /// Canonicalise `path` and verify it is inside the allowed root.
    fn safe_path(&self, path: impl AsRef<Path>) -> Result<PathBuf, OperationError> {
        let path = path.as_ref();
        // Resolve the path relative to root if it is relative
        let resolved = if path.is_relative() {
            self.root.join(path)
        } else {
            path.to_path_buf()
        };

        // Canonicalize (follows symlinks, resolves `..`)
        let canonical = resolved.canonicalize().map_err(|_| OperationError::PathTraversal {
            path: path.to_path_buf(),
        })?;

        if canonical.starts_with(&self.root) {
            Ok(canonical)
        } else {
            error!(
                "[ide-fs] path traversal blocked: {} (root: {})",
                canonical.display(),
                self.root.display()
            );
            Err(OperationError::OutsideRoot { path: canonical })
        }
    }

    // ── File operations ──────────────────────────────────────────────

    /// Read the entire contents of a file into a byte vector.
    pub async fn read(&self, path: impl AsRef<Path>) -> Result<Vec<u8>, OperationError> {
        let safe = self.safe_path(path)?;
        Ok(fs::read(&safe).await?)
    }

    /// Read a file as a string.
    pub async fn read_string(&self, path: impl AsRef<Path>) -> Result<String, OperationError> {
        let safe = self.safe_path(path)?;
        Ok(fs::read_to_string(&safe).await?)
    }

    /// Write bytes to a file, creating parent directories if needed.
    pub async fn write(
        &self,
        path: impl AsRef<Path>,
        content: impl AsRef<[u8]>,
    ) -> Result<(), OperationError> {
        let safe = self.safe_path(path)?;
        if let Some(parent) = safe.parent() {
            fs::create_dir_all(parent).await?;
        }
        Ok(fs::write(&safe, content).await?)
    }

    /// Move (rename) a file or directory.
    pub async fn move_path(
        &self,
        from: impl AsRef<Path>,
        to: impl AsRef<Path>,
    ) -> Result<(), OperationError> {
        let safe_from = self.safe_path(from)?;
        let safe_to = self.safe_path(to)?;
        if let Some(parent) = safe_to.parent() {
            fs::create_dir_all(parent).await?;
        }
        Ok(fs::rename(&safe_from, &safe_to).await?)
    }

    /// Copy a file from `from` to `to`.
    pub async fn copy(
        &self,
        from: impl AsRef<Path>,
        to: impl AsRef<Path>,
    ) -> Result<u64, OperationError> {
        let safe_from = self.safe_path(from)?;
        let safe_to = self.safe_path(to)?;
        if let Some(parent) = safe_to.parent() {
            fs::create_dir_all(parent).await?;
        }
        Ok(fs::copy(&safe_from, &safe_to).await?)
    }

    /// Delete a file or empty directory.
    pub async fn delete(&self, path: impl AsRef<Path>) -> Result<(), OperationError> {
        let safe = self.safe_path(path)?;
        if safe.is_dir() {
            fs::remove_dir(&safe).await?;
        } else {
            fs::remove_file(&safe).await?;
        }
        Ok(())
    }

    /// Recursively remove a directory.
    pub async fn delete_all(&self, path: impl AsRef<Path>) -> Result<(), OperationError> {
        let safe = self.safe_path(path)?;
        fs::remove_dir_all(&safe).await?;
        Ok(())
    }

    /// Check if a path exists.
    pub async fn exists(&self, path: impl AsRef<Path>) -> Result<bool, OperationError> {
        let safe = self.safe_path(path)?;
        Ok(safe.exists())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::fs as async_fs;

    #[tokio::test]
    async fn test_path_traversal_blocked() {
        let dir = std::env::temp_dir().join("ide-fs-ops-test");
        let _ = async_fs::remove_dir_all(&dir).await;
        async_fs::create_dir_all(&dir).await.unwrap();

        let ops = FileOperations::new(&dir).unwrap();

        let result = ops.read("../etc/passwd").await;
        assert!(result.is_err(), "path traversal should be blocked");

        let _ = async_fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn test_write_and_read() {
        let dir = std::env::temp_dir().join("ide-fs-ops-rw-test");
        let _ = async_fs::remove_dir_all(&dir).await;

        let ops = FileOperations::new(&dir).unwrap();

        let path = "hello.txt";
        ops.write(path, b"Hello, world!").await.unwrap();
        let content = ops.read_string(path).await.unwrap();
        assert_eq!(content, "Hello, world!");

        let _ = async_fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn test_copy_and_delete() {
        let dir = std::env::temp_dir().join("ide-fs-ops-cp-test");
        let _ = async_fs::remove_dir_all(&dir).await;
        async_fs::create_dir_all(&dir).await.unwrap();

        let ops = FileOperations::new(&dir).unwrap();

        ops.write("src.txt", b"source").await.unwrap();
        ops.copy("src.txt", "dst.txt").await.unwrap();
        assert!(ops.exists("dst.txt").await.unwrap());

        ops.delete("src.txt").await.unwrap();
        assert!(!ops.exists("src.txt").await.unwrap());

        let _ = async_fs::remove_dir_all(&dir).await;
    }
}
