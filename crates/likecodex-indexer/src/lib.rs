use anyhow::Result;
use ignore::WalkBuilder;
use serde::{Deserialize, Serialize};
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::path::{Path, PathBuf};
use tracing::{debug, info};

/// Lightweight file index for a repository with optional disk cache.
#[derive(Debug, Default, Serialize, Deserialize)]
pub struct FileIndex {
    pub files: Vec<FileEntry>,
    pub root: Option<PathBuf>,
    pub indexed_at: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileEntry {
    pub path: PathBuf,
    pub language: Option<String>,
    pub size: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SymbolEntry {
    pub path: PathBuf,
    pub name: String,
    pub kind: String,
    pub line: u32,
}

impl FileIndex {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn cache_path(root: impl AsRef<Path>) -> PathBuf {
        root.as_ref().join(".likecodex").join("file_index.json")
    }

    pub fn load_cached(root: impl AsRef<Path>) -> Option<Self> {
        let path = Self::cache_path(&root);
        let text = std::fs::read_to_string(path).ok()?;
        serde_json::from_str(&text).ok()
    }

    pub fn save_cached(&self, root: impl AsRef<Path>) -> Result<()> {
        let path = Self::cache_path(&root);
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(path, serde_json::to_string_pretty(self)?)?;
        Ok(())
    }

    pub fn index(&mut self, root: impl AsRef<Path>) -> Result<()> {
        let root = root.as_ref();
        info!(root = %root.display(), "indexing repository");
        self.files.clear();
        self.root = Some(root.to_path_buf());
        self.indexed_at = Some(
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0),
        );

        let walker = WalkBuilder::new(root)
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

    pub fn index_or_load(&mut self, root: impl AsRef<Path>) -> Result<()> {
        let root = root.as_ref();
        if let Some(cached) = Self::load_cached(root) {
            if cached.root.as_deref() == Some(root) {
                *self = cached;
                return Ok(());
            }
        }
        self.index(root)?;
        let _ = self.save_cached(root);
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

    pub fn symbols_for_path(&self, path: &Path) -> Vec<SymbolEntry> {
        let Ok(content) = std::fs::read_to_string(path) else {
            return vec![];
        };
        let mut symbols = Vec::new();
        for (idx, line) in content.lines().enumerate() {
            let trimmed = line.trim();
            if trimmed.starts_with("def ") {
                if let Some(name) = trimmed.strip_prefix("def ").and_then(|s| s.split('(').next()) {
                    symbols.push(SymbolEntry {
                        path: path.to_path_buf(),
                        name: name.to_string(),
                        kind: "function".to_string(),
                        line: (idx + 1) as u32,
                    });
                }
            } else if trimmed.starts_with("class ") {
                if let Some(name) = trimmed.strip_prefix("class ").and_then(|s| s.split(['(', ':', ' ']).next()) {
                    symbols.push(SymbolEntry {
                        path: path.to_path_buf(),
                        name: name.to_string(),
                        kind: "class".to_string(),
                        line: (idx + 1) as u32,
                    });
                }
            } else if trimmed.starts_with("pub fn ") || trimmed.starts_with("fn ") {
                let rest = trimmed.trim_start_matches("pub ").trim_start_matches("fn ");
                if let Some(name) = rest.split(['(', '<']).next() {
                    symbols.push(SymbolEntry {
                        path: path.to_path_buf(),
                        name: name.trim().to_string(),
                        kind: "function".to_string(),
                        line: (idx + 1) as u32,
                    });
                }
            }
        }
        symbols
    }

    pub fn fingerprint(&self) -> u64 {
        let mut hasher = DefaultHasher::new();
        self.files.len().hash(&mut hasher);
        hasher.finish()
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
