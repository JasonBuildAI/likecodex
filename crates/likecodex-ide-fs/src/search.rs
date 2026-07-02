use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use walkdir::WalkDir;
use glob::Pattern;
use tracing::warn;

use crate::filter::FileFilter;

/// The result of a search operation.
#[derive(Debug, Clone)]
pub struct SearchResult {
    /// Absolute path to the matching file.
    pub path: PathBuf,
    /// The line number (1-based) for content matches, or 0 for name/glob matches.
    pub line_number: usize,
    /// The matching line content (for content matches), or the file name.
    pub line: String,
}

/// Recursive file search engine.
///
/// Supports three kinds of search:
/// - **Glob** matching (e.g. `**&#47;*.rs`)
/// - **Name** matching (substring, case-insensitive)
/// - **Content** matching (substring search within file contents)
#[derive(Debug, Clone)]
pub struct FileSearcher {
    root: PathBuf,
    filter: Arc<FileFilter>,
}

impl FileSearcher {
    /// Create a new searcher rooted at `root`.
    ///
    /// Files that are filtered out by `filter` will be skipped during traversal.
    pub fn new(root: impl Into<PathBuf>, filter: FileFilter) -> Self {
        Self {
            root: root.into(),
            filter: Arc::new(filter),
        }
    }

    /// Return the root directory.
    pub fn root(&self) -> &Path {
        &self.root
    }

    // ── Glob search ─────────────────────────────────────────────────

    /// Find all files matching a glob pattern, searched relative to `root`.
    ///
    /// Example: `search_glob("**&#47;*.rs")` finds all Rust source files.
    pub fn search_glob(&self, glob_pattern: &str) -> Vec<SearchResult> {
        let pattern = match Pattern::new(glob_pattern) {
            Ok(p) => p,
            Err(e) => {
                warn!("[ide-fs::search] invalid glob pattern '{glob_pattern}': {e}");
                return Vec::new();
            }
        };

        let mut results = Vec::new();
        for entry in WalkDir::new(&self.root)
            .follow_links(false)
            .into_iter()
            .filter_entry(|e| self.filter.accept(e.path()))
        {
            match entry {
                Ok(entry) if entry.file_type().is_file() => {
                    let rel_path = entry.path().strip_prefix(&self.root).unwrap_or(entry.path());
                    if pattern.matches_path(rel_path) || pattern.matches_path(entry.path()) {
                        results.push(SearchResult {
                            path: entry.path().to_path_buf(),
                            line_number: 0,
                            line: entry.file_name().to_string_lossy().to_string(),
                        });
                    }
                }
                Err(e) => {
                    warn!("[ide-fs::search] walk error: {e}");
                }
                _ => {}
            }
        }
        results
    }

    // ── Name search ─────────────────────────────────────────────────

    /// Find all files whose name contains `query` (case-insensitive).
    pub fn search_name(&self, query: &str) -> Vec<SearchResult> {
        let query_lower = query.to_lowercase();
        let mut results = Vec::new();

        for entry in WalkDir::new(&self.root)
            .follow_links(false)
            .into_iter()
            .filter_entry(|e| self.filter.accept(e.path()))
        {
            match entry {
                Ok(entry) if entry.file_type().is_file() => {
                    let name = entry.file_name().to_string_lossy();
                    if name.to_lowercase().contains(&query_lower) {
                        results.push(SearchResult {
                            path: entry.path().to_path_buf(),
                            line_number: 0,
                            line: name.to_string(),
                        });
                    }
                }
                Err(e) => {
                    warn!("[ide-fs::search] walk error: {e}");
                }
                _ => {}
            }
        }
        results
    }

    // ── Content search ──────────────────────────────────────────────

    /// Search file contents for lines containing `query`.
    ///
    /// This is a simple substring match (case-insensitive by default).
    /// For advanced regex matching, consider building on top of this.
    ///
    /// `max_results` limits the total number of results returned (0 = unlimited).
    /// `max_file_size` limits individual file reads (bytes, default 10 MiB).
    pub fn search_content(
        &self,
        query: &str,
        max_results: usize,
        max_file_size: Option<u64>,
    ) -> Vec<SearchResult> {
        let query_lower = query.to_lowercase();
        let max_size = max_file_size.unwrap_or(10 * 1024 * 1024); // 10 MiB default
        let mut results = Vec::new();

        for entry in WalkDir::new(&self.root)
            .follow_links(false)
            .into_iter()
            .filter_entry(|e| self.filter.accept(e.path()))
        {
            if let Ok(entry) = entry {
                if !entry.file_type().is_file() {
                    continue;
                }

                // Skip large files
                if let Ok(meta) = entry.metadata() {
                    if meta.len() > max_size {
                        continue;
                    }
                }

                // Read the file and search line by line
                match fs::read_to_string(entry.path()) {
                    Ok(content) => {
                        for (i, line) in content.lines().enumerate() {
                            if line.to_lowercase().contains(&query_lower) {
                                results.push(SearchResult {
                                    path: entry.path().to_path_buf(),
                                    line_number: i + 1,
                                    line: line.to_string(),
                                });
                                if max_results > 0 && results.len() >= max_results {
                                    return results;
                                }
                            }
                        }
                    }
                    Err(e) => {
                        warn!(
                            "[ide-fs::search] failed to read {}: {e}",
                            entry.path().display()
                        );
                    }
                }
            }
        }
        results
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::filter::FileFilter;

    fn setup_test_dir(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("ide-fs-search-{name}"));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        fs::write(dir.join("main.rs"), b"fn main() {\n    println!(\"hello\");\n}\n").unwrap();
        fs::write(dir.join("lib.rs"), b"pub fn greet() -> &str { \"hello\" }\n").unwrap();
        fs::write(dir.join("README.md"), b"# Hello World\n").unwrap();
        fs::write(dir.join("data.txt"), b"some data\n").unwrap();
        dir
    }

    #[test]
    fn test_glob_search() {
        let dir = setup_test_dir("glob");
        let searcher = FileSearcher::new(&dir, FileFilter::empty());
        let results = searcher.search_glob("**/*.rs");
        assert_eq!(results.len(), 2);
        let names: Vec<_> = results.iter().map(|r| r.line.as_str()).collect();
        assert!(names.contains(&"main.rs"));
        assert!(names.contains(&"lib.rs"));
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_name_search() {
        let dir = setup_test_dir("name");
        let searcher = FileSearcher::new(&dir, FileFilter::empty());
        let results = searcher.search_name("readme");
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].line, "README.md");
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_content_search() {
        let dir = setup_test_dir("content");
        let searcher = FileSearcher::new(&dir, FileFilter::empty());
        let results = searcher.search_content("hello", 0, None);
        assert!(results.len() >= 2); // main.rs and lib.rs and README.md all contain "hello"
        let _ = fs::remove_dir_all(&dir);
    }
}
