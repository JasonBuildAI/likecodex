use ignore::gitignore::{Gitignore, GitignoreBuilder};
use ignore::Match;
use std::path::Path;
use tracing::warn;

#[derive(Debug, Clone)]
pub struct FileFilter {
    gitignore: Gitignore,
    extra_patterns: Vec<String>,
}

impl FileFilter {
    pub fn new(root: impl AsRef<Path>, extra_globs: &[String]) -> Self {
        let root = root.as_ref();
        let mut builder = GitignoreBuilder::new(root);
        let gitignore_path = root.join(".gitignore");
        if gitignore_path.exists() {
            if let Some(err) = builder.add(gitignore_path) {
                warn!("[ide-fs::filter] failed to load .gitignore: {err}");
            }
        }
        for glob in extra_globs {
            if let Err(e) = builder.add_line(None, glob) {
                warn!("[ide-fs::filter] invalid extra glob pattern '{glob}': {e}");
            }
        }
        let gitignore = builder.build().unwrap_or(Gitignore::empty());
        Self { gitignore, extra_patterns: extra_globs.to_vec() }
    }

    pub fn empty() -> Self {
        Self { gitignore: Gitignore::empty(), extra_patterns: Vec::new() }
    }

    pub fn accept(&self, path: impl AsRef<Path>) -> bool {
        let path = path.as_ref();
        match self.gitignore.matched(path, path.is_dir()) {
            Match::Whitelist(_) => true,
            Match::Ignore(_) => false,
            Match::None => true,
        }
    }

    pub fn extra_patterns(&self) -> &[String] {
        &self.extra_patterns
    }
}
