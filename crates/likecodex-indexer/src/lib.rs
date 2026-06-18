use anyhow::Result;
use ignore::WalkBuilder;
use std::path::{Path, PathBuf};
use tracing::{debug, info};

/// Lightweight file index for a repository.
#[derive(Debug, Default)]
pub struct FileIndex {
    pub files: Vec<FileEntry>,
}

#[derive(Debug, Clone)]
pub struct FileEntry {
    pub path: PathBuf,
    pub language: Option<String>,
    pub size: u64,
}

impl FileIndex {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn index(&mut self, root: impl AsRef<Path>) -> Result<()> {
        info!(root = %root.as_ref().display(), "indexing repository");
        self.files.clear();
        let walker = WalkBuilder::new(&root)
            .hidden(false)
            .git_ignore(true)
            .git_global(true)
            .build();

        for entry in walker {
            let entry = entry?;
            if !entry.file_type().map(|t| t.is_file()).unwrap_or(false) {
                continue;
            }
            let path = entry.path().to_path_buf();
            let size = std::fs::metadata(&path).map(|m| m.len()).unwrap_or(0);
            let language = detect_language(&path);
            self.files.push(FileEntry {
                path,
                language,
                size,
            });
        }

        debug!(count = self.files.len(), "indexing complete");
        Ok(())
    }

    pub fn search_by_name(&self, pattern: &str) -> Vec<&FileEntry> {
        self.files
            .iter()
            .filter(|f| {
                f.path
                    .file_name()
                    .and_then(|n| n.to_str())
                    .map(|n| n.contains(pattern))
                    .unwrap_or(false)
            })
            .collect()
    }
}

fn detect_language(path: &Path) -> Option<String> {
    path.extension()
        .and_then(|e| e.to_str())
        .map(|ext| match ext {
            "rs" => "rust",
            "py" => "python",
            "js" | "jsx" => "javascript",
            "ts" | "tsx" => "typescript",
            "go" => "go",
            "java" => "java",
            "cpp" | "cc" | "hpp" => "cpp",
            "c" | "h" => "c",
            "md" => "markdown",
            "toml" => "toml",
            "json" => "json",
            "yaml" | "yml" => "yaml",
            _ => "unknown",
        })
        .map(|s| s.to_string())
}
