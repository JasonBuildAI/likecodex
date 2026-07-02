use std::path::Path;
use ignore::gitignore::{Gitignore, GitignoreBuilder};
use tracing::warn;

/// A file filter that combines `.gitignore` rules with extra glob patterns.
///
/// Filtering is permissive: if a path is not matched by any rule it is **accepted**.
/// This makes it suitable for whitelisting as well as blacklisting.
#[derive(Debug, Clone)]
pub struct FileFilter {
    /// The compiled gitignore matcher.
    gitignore: Gitignore,
    /// Additional glob patterns (e.g. `*.log`, `build/`).
    extra_patterns: Vec<String>,
}

impl FileFilter {
    /// Build a filter rooted at `root`.
    ///
    /// The root directory is scanned for `.gitignore` files automatically
    /// (ignoring `target/`, `.git/`, etc. which the `ignore` crate handles).
    ///
    /// `extra_globs` are additional patterns applied on top of `.gitignore`.
    /// They follow the same syntax as `.gitignore` patterns.
    pub fn new(root: impl AsRef<Path>, extra_globs: &[String]) -> Self {
        let root = root.as_ref();
        let mut builder = GitignoreBuilder::new(root);

        // Load project-level .gitignore
        let gitignore_path = root.join(".gitignore");
        if gitignore_path.exists() {
            if let Err(e) = builder.add(gitignore_path) {
                warn!("[ide-fs::filter] failed to load .gitignore: {e}");
            }
        }

        // Add extra globs as individual patterns
        for glob in extra_globs {
            builder.add_line(None, glob).unwrap_or_else(|e| {
                warn!("[ide-fs::filter] invalid extra glob pattern '{glob}': {e}");
                false
            });
        }

        let gitignore = builder.build().unwrap_or(Gitignore::empty());
        Self {
            gitignore,
            extra_patterns: extra_globs.to_vec(),
        }
    }

    /// Create a filter with no `.gitignore` rules.
    pub fn empty() -> Self {
        Self {
            gitignore: Gitignore::empty(),
            extra_patterns: Vec::new(),
        }
    }

    /// Returns `true` if the path should be **included** (not filtered out).
    ///
    /// A path is rejected when:
    ///   - The gitignore rules match it as ignored (`is_ignore`), **and**
    ///   - No whitelist exception (`is_whitelist`) applies.
    ///
    /// If no rule matches at all the path is accepted.
    pub fn accept(&self, path: impl AsRef<Path>) -> bool {
        let path = path.as_ref();
        let (is_ignore, is_whitelist) = self.gitignore.matched(path, path.is_dir());

        // If .gitignore explicitly whitelists it, always accept
        if is_whitelist {
            return true;
        }

        // If .gitignore ignores it, reject
        if is_ignore {
            return false;
        }

        // No rule => accept
        true
    }

    /// Return the extra glob patterns configured on this filter.
    pub fn extra_patterns(&self) -> &[String] {
        &self.extra_patterns
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn test_gitignore_filter() {
        let dir = std::env::temp_dir().join("ide-fs-filter-test");
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();

        // Write a .gitignore
        fs::write(dir.join(".gitignore"), b"*.log\n").unwrap();

        let filter = FileFilter::new(&dir, &[]);

        let accepted = dir.join("main.rs");
        let rejected = dir.join("debug.log");

        assert!(filter.accept(&accepted), "main.rs should be accepted");
        assert!(!filter.accept(&rejected), "debug.log should be rejected");

        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_extra_glob() {
        let dir = std::env::temp_dir().join("ide-fs-filter-glob-test");
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();

        let extra = vec!["build/".to_string()];
        let filter = FileFilter::new(&dir, &extra);

        let build_path = dir.join("build").join("output.o");
        assert!(!filter.accept(&build_path), "build/ should be rejected by extra glob");

        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_empty_filter_accepts_all() {
        let filter = FileFilter::empty();
        assert!(filter.accept("/any/path/file.rs"));
        assert!(filter.accept("/tmp/debug.log"));
    }
}
