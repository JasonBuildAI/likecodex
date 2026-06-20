use anyhow::Result;
use ignore::WalkBuilder;
use serde::{Deserialize, Serialize};
use std::collections::hash_map::DefaultHasher;
use std::collections::HashMap;
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
        extract_symbols(path, &content)
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

/// Extract coarse symbol definitions from a file's content using language-aware
/// line heuristics. Mirrors the Python `codegraph` builder so CLI and engine
/// agree on symbol shapes.
pub fn extract_symbols(path: &Path, content: &str) -> Vec<SymbolEntry> {
    let lang = detect_language(path).unwrap_or_else(|| "unknown".to_string());
    let mut symbols = Vec::new();
    for (idx, line) in content.lines().enumerate() {
        let trimmed = line.trim_start();
        let line_no = (idx + 1) as u32;
        let mut push = |name: &str, kind: &str| {
            let clean = name.trim();
            if !clean.is_empty() {
                symbols.push(SymbolEntry {
                    path: path.to_path_buf(),
                    name: clean.to_string(),
                    kind: kind.to_string(),
                    line: line_no,
                });
            }
        };
        match lang.as_str() {
            "python" => {
                if let Some(rest) = trimmed.strip_prefix("def ") {
                    if let Some(name) = rest.split('(').next() {
                        push(name, "function");
                    }
                } else if let Some(rest) = trimmed.strip_prefix("class ") {
                    if let Some(name) = rest.split(['(', ':', ' ']).next() {
                        push(name, "class");
                    }
                }
            }
            "rust" => {
                let rest = trimmed
                    .trim_start_matches("pub ")
                    .trim_start_matches("async ");
                if let Some(name) = rest
                    .strip_prefix("fn ")
                    .and_then(|s| s.split(['(', '<']).next())
                {
                    push(name, "function");
                } else if let Some(name) = rest
                    .strip_prefix("struct ")
                    .and_then(|s| s.split([' ', '<', '{', '(', ';']).next())
                {
                    push(name, "struct");
                } else if let Some(name) = rest
                    .strip_prefix("enum ")
                    .and_then(|s| s.split([' ', '<', '{']).next())
                {
                    push(name, "enum");
                } else if let Some(name) = rest
                    .strip_prefix("trait ")
                    .and_then(|s| s.split([' ', '<', '{']).next())
                {
                    push(name, "trait");
                }
            }
            "javascript" | "typescript" => {
                let rest = trimmed
                    .trim_start_matches("export ")
                    .trim_start_matches("default ")
                    .trim_start_matches("async ");
                if let Some(name) = rest
                    .strip_prefix("function ")
                    .and_then(|s| s.split(['(', '<', ' ']).next())
                {
                    push(name, "function");
                } else if let Some(name) = rest
                    .strip_prefix("class ")
                    .and_then(|s| s.split([' ', '<', '{']).next())
                {
                    push(name, "class");
                } else if let Some(name) = rest
                    .strip_prefix("interface ")
                    .and_then(|s| s.split([' ', '<', '{']).next())
                {
                    push(name, "interface");
                } else if let Some(name) = rest
                    .strip_prefix("type ")
                    .and_then(|s| s.split([' ', '=', '<']).next())
                {
                    push(name, "type");
                }
            }
            "go" => {
                if let Some(rest) = trimmed.strip_prefix("func ") {
                    // Skip an optional receiver: func (r *T) Name(...)
                    let after_receiver = if rest.starts_with('(') {
                        rest.split(')').nth(1).unwrap_or(rest).trim_start()
                    } else {
                        rest
                    };
                    if let Some(name) = after_receiver.split('(').next() {
                        push(name, "function");
                    }
                } else if let Some(rest) = trimmed.strip_prefix("type ") {
                    let mut parts = rest.split_whitespace();
                    if let Some(name) = parts.next() {
                        let kind = match parts.next() {
                            Some("interface") => "interface",
                            _ => "struct",
                        };
                        push(name, kind);
                    }
                }
            }
            "java" => {
                if let Some(pos) = trimmed.find("class ") {
                    if let Some(name) = trimmed[pos + 6..].split([' ', '<', '{']).next() {
                        push(name, "class");
                    }
                } else if let Some(pos) = trimmed.find("interface ") {
                    if let Some(name) = trimmed[pos + 10..].split([' ', '<', '{']).next() {
                        push(name, "interface");
                    }
                }
            }
            _ => {}
        }
    }
    symbols
}

/// A symbol + reference graph for a repository, persisted alongside the file
/// index so CLI commands and background reindexing can share it.
#[derive(Debug, Default, Serialize, Deserialize)]
pub struct CodeGraph {
    pub symbols: Vec<SymbolEntry>,
    pub references: HashMap<String, Vec<String>>,
    pub root: Option<PathBuf>,
    pub file_count: usize,
}

impl CodeGraph {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn cache_path(root: impl AsRef<Path>) -> PathBuf {
        root.as_ref().join(".likecodex").join("codegraph.json")
    }

    pub fn build(&mut self, root: impl AsRef<Path>) -> Result<()> {
        let root = root.as_ref();
        info!(root = %root.display(), "building code graph");
        self.symbols.clear();
        self.references.clear();
        self.root = Some(root.to_path_buf());

        let walker = WalkBuilder::new(root)
            .hidden(false)
            .git_ignore(true)
            .git_global(true)
            .build();

        let mut files: Vec<PathBuf> = Vec::new();
        for entry in walker.flatten() {
            if !entry.file_type().map(|t| t.is_file()).unwrap_or(false) {
                continue;
            }
            let path = entry.path();
            let lang = detect_language(path);
            if matches!(
                lang.as_deref(),
                Some("rust" | "python" | "javascript" | "typescript" | "go" | "java")
            ) {
                files.push(path.to_path_buf());
            }
        }

        let mut defined: std::collections::HashSet<String> = std::collections::HashSet::new();
        for path in &files {
            if let Ok(content) = std::fs::read_to_string(path) {
                for sym in extract_symbols(path, &content) {
                    defined.insert(sym.name.clone());
                    self.symbols.push(sym);
                }
            }
        }

        for path in &files {
            let Ok(content) = std::fs::read_to_string(path) else {
                continue;
            };
            let rel = path
                .strip_prefix(root)
                .unwrap_or(path)
                .display()
                .to_string();
            for (idx, line) in content.lines().enumerate() {
                for name in call_idents(line) {
                    if defined.contains(&name) {
                        self.references.entry(name).or_default().push(format!(
                            "{}:{}",
                            rel,
                            idx + 1
                        ));
                    }
                }
            }
        }

        self.file_count = files.len();
        debug!(
            symbols = self.symbols.len(),
            files = self.file_count,
            "code graph built"
        );
        Ok(())
    }

    pub fn save_cached(&self, root: impl AsRef<Path>) -> Result<()> {
        let path = Self::cache_path(&root);
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(path, serde_json::to_string(self)?)?;
        Ok(())
    }

    pub fn search(&self, name: &str) -> Vec<&SymbolEntry> {
        let lowered = name.to_lowercase();
        self.symbols
            .iter()
            .filter(|s| s.name.to_lowercase().contains(&lowered))
            .collect()
    }
}

/// Return identifiers that appear immediately before a `(` on a line.
fn call_idents(line: &str) -> Vec<String> {
    let mut idents = Vec::new();
    let bytes = line.as_bytes();
    let mut start: Option<usize> = None;
    for (i, &b) in bytes.iter().enumerate() {
        let is_ident = b == b'_' || b.is_ascii_alphanumeric();
        if is_ident {
            if start.is_none() {
                start = Some(i);
            }
        } else {
            if b == b'(' {
                if let Some(s) = start {
                    let word = &line[s..i];
                    if word
                        .chars()
                        .next()
                        .map(|c| c == '_' || c.is_ascii_alphabetic())
                        .unwrap_or(false)
                    {
                        idents.push(word.to_string());
                    }
                }
            }
            start = None;
        }
    }
    idents
}
