use serde::{Deserialize, Serialize};

/// Policy controlling sandbox resource limits and permissions.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SandboxPolicy {
    /// Maximum execution time in seconds.
    pub timeout_secs: u64,
    /// Memory limit in megabytes.
    pub memory_mb: Option<u64>,
    /// Maximum number of CPUs.
    pub max_cpus: Option<f64>,
    /// Whether the sandbox is allowed network access.
    pub allow_network: bool,
    /// Directories that may be mounted read-only (absolute host paths).
    pub read_only_mounts: Vec<String>,
    /// Directories that may be mounted read-write (absolute host paths).
    pub read_write_mounts: Vec<String>,
}

impl Default for SandboxPolicy {
    fn default() -> Self {
        Self {
            timeout_secs: 120,
            memory_mb: Some(512),
            max_cpus: Some(1.0),
            allow_network: false,
            read_only_mounts: Vec::new(),
            read_write_mounts: Vec::new(),
        }
    }
}

impl SandboxPolicy {
    pub fn permissive() -> Self {
        Self {
            timeout_secs: 300,
            memory_mb: Some(2048),
            max_cpus: Some(2.0),
            allow_network: true,
            read_only_mounts: Vec::new(),
            read_write_mounts: Vec::new(),
        }
    }

    pub fn strict() -> Self {
        Self {
            timeout_secs: 60,
            memory_mb: Some(256),
            max_cpus: Some(1.0),
            allow_network: false,
            read_only_mounts: Vec::new(),
            read_write_mounts: Vec::new(),
        }
    }
}
