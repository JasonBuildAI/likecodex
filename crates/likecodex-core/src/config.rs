use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};

/// Root configuration for LikeCodex.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Config {
    #[serde(default)]
    pub llm: LlmConfig,
    #[serde(default)]
    pub deepseek: DeepSeekConfig,
    #[serde(default)]
    pub approval: ApprovalConfig,
    #[serde(default)]
    pub sandbox: SandboxConfig,
    #[serde(default)]
    pub mcp: McpConfig,
    #[serde(default)]
    pub server: ServerConfig,
    #[serde(default)]
    pub agent: AgentConfig,
}

impl Config {
    /// Load merged config: user → project ancestors → optional explicit path.
    pub fn load() -> anyhow::Result<Self> {
        Self::load_resolved(None, std::env::current_dir().ok().as_deref())
    }

    pub fn load_from(path: impl AsRef<Path>) -> anyhow::Result<Self> {
        Self::load_resolved(Some(path.as_ref()), std::env::current_dir().ok().as_deref())
    }

    pub fn load_resolved(explicit: Option<&Path>, cwd: Option<&Path>) -> anyhow::Result<Self> {
        let mut merged = toml::Value::Table(toml::map::Map::new());

        let user_path = Self::default_path();
        if user_path.exists() {
            merge_toml(&mut merged, parse_toml_file(&user_path)?);
        }

        if let Some(cwd) = cwd {
            for path in project_config_paths(cwd) {
                merge_toml(&mut merged, parse_toml_file(&path)?);
            }
        }

        if let Some(path) = explicit {
            merge_toml(&mut merged, parse_toml_file(path)?);
        }

        value_to_config(merged)
    }

    pub fn default_path() -> PathBuf {
        dirs::home_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join(".likecodex")
            .join("config.toml")
    }

    pub fn save_user(&self) -> anyhow::Result<PathBuf> {
        let path = Self::default_path();
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let content = toml::to_string_pretty(self)?;
        std::fs::write(&path, content)?;
        Ok(path)
    }
}

fn parse_toml_file(path: &Path) -> anyhow::Result<toml::Value> {
    let content = std::fs::read_to_string(path)?;
    Ok(toml::from_str(&content)?)
}

fn merge_toml(base: &mut toml::Value, overlay: toml::Value) {
    match (base, overlay) {
        (toml::Value::Table(base_tbl), toml::Value::Table(overlay_tbl)) => {
            for (key, value) in overlay_tbl {
                if let Some(existing) = base_tbl.get_mut(&key) {
                    merge_toml(existing, value);
                } else {
                    base_tbl.insert(key, value);
                }
            }
        }
        (base_slot, overlay) => *base_slot = overlay,
    }
}

fn value_to_config(value: toml::Value) -> anyhow::Result<Config> {
    let content = toml::to_string(&value)?;
    let mut cfg: Config = toml::from_str(&content)?;
    cfg.llm.resolve_api_key();
    cfg.server.resolve_api_token();
    Ok(cfg)
}

/// Project config files from repo root toward `cwd` (later entries override earlier).
pub fn project_config_paths(cwd: &Path) -> Vec<PathBuf> {
    let mut dir = cwd.to_path_buf();
    let mut stack: Vec<PathBuf> = Vec::new();
    loop {
        for name in [".likecodex/config.toml", "likecodex.toml"] {
            let candidate = dir.join(name);
            if candidate.exists() {
                stack.push(candidate);
            }
        }
        if !dir.pop() {
            break;
        }
    }
    stack.reverse();
    stack
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LlmConfig {
    pub provider: String,
    pub model: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub api_key: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub base_url: Option<String>,
    #[serde(default)]
    pub temperature: f32,
    #[serde(default = "default_max_tokens")]
    pub max_tokens: u32,
}

impl Default for LlmConfig {
    fn default() -> Self {
        Self {
            provider: "deepseek".to_string(),
            model: "deepseek-v4-flash".to_string(),
            api_key: None,
            base_url: Some("https://api.deepseek.com".to_string()),
            temperature: 0.0,
            max_tokens: default_max_tokens(),
        }
    }
}

impl LlmConfig {
    fn resolve_api_key(&mut self) {
        if self.api_key.is_none() {
            if let Ok(key) = std::env::var("DEEPSEEK_API_KEY") {
                self.api_key = Some(key);
                return;
            }
            if let Ok(key) = std::env::var("LIKECODEX_LLM_API_KEY") {
                self.api_key = Some(key);
                return;
            }
            let env_var = format!("{}_API_KEY", self.provider.to_uppercase());
            self.api_key = std::env::var(&env_var).ok();
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeepSeekConfig {
    #[serde(default = "default_false")]
    pub thinking: bool,
    #[serde(default)]
    pub reasoning_effort: Option<String>,
    #[serde(default)]
    pub reasoning_language: Option<String>,
}

impl Default for DeepSeekConfig {
    fn default() -> Self {
        Self {
            thinking: false,
            reasoning_effort: None,
            reasoning_language: None,
        }
    }
}

fn default_max_tokens() -> u32 {
    4096
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApprovalConfig {
    #[serde(default = "default_approval_mode")]
    pub mode: String,
}

impl Default for ApprovalConfig {
    fn default() -> Self {
        Self {
            mode: default_approval_mode(),
        }
    }
}

fn default_approval_mode() -> String {
    "auto".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SandboxConfig {
    #[serde(default = "default_true")]
    pub enabled: bool,
    pub image: Option<String>,
    #[serde(default)]
    pub network: bool,
    #[serde(default = "default_false")]
    pub allow_network: bool,
    #[serde(default = "default_timeout_secs")]
    pub timeout_secs: Option<u64>,
    #[serde(default)]
    pub memory_mb: Option<u64>,
    #[serde(default)]
    pub max_cpus: Option<f64>,
    #[serde(default)]
    pub writable_roots: Vec<PathBuf>,
    #[serde(default = "default_true")]
    pub allow_fallback: bool,
}

impl Default for SandboxConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            image: Some("likecodex/sandbox:latest".to_string()),
            network: false,
            allow_network: false,
            timeout_secs: Some(120),
            memory_mb: Some(512),
            max_cpus: Some(1.0),
            writable_roots: vec![],
            allow_fallback: true,
        }
    }
}

impl SandboxConfig {
    /// Effective network permission: either legacy `network` or `allow_network` may enable it.
    pub fn allow_network(&self) -> bool {
        self.network || self.allow_network
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct McpConfig {
    #[serde(default = "default_false")]
    pub enabled: bool,
    #[serde(default = "default_mcp_startup")]
    pub startup: String,
    #[serde(default)]
    pub servers: HashMap<String, McpServerConfig>,
}

fn default_mcp_startup() -> String {
    "lazy".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct McpServerConfig {
    pub command: String,
    #[serde(default)]
    pub args: Vec<String>,
    #[serde(default)]
    pub env: HashMap<String, String>,
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default)]
    pub startup: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerConfig {
    #[serde(default = "default_host")]
    pub host: String,
    #[serde(default = "default_port")]
    pub port: u16,
    #[serde(default)]
    pub engine_url: Option<String>,
    #[serde(default)]
    pub api_token: Option<String>,
}

impl Default for ServerConfig {
    fn default() -> Self {
        Self {
            host: default_host(),
            port: default_port(),
            engine_url: None,
            api_token: None,
        }
    }
}

fn default_host() -> String {
    "127.0.0.1".to_string()
}

fn default_port() -> u16 {
    8080
}

fn default_true() -> bool {
    true
}

fn default_false() -> bool {
    false
}

fn default_timeout_secs() -> Option<u64> {
    Some(120)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentConfig {
    #[serde(default = "default_max_steps")]
    pub max_steps: u32,
    #[serde(default)]
    pub planner_model: Option<String>,
    #[serde(default)]
    pub executor_model: Option<String>,
    #[serde(default = "default_planner_max_steps")]
    pub planner_max_steps: u32,
    #[serde(default = "default_compact_ratio")]
    pub compact_ratio: f32,
    #[serde(default = "default_false")]
    pub enable_planner: bool,
    #[serde(default = "default_auto_plan")]
    pub auto_plan: String,
    #[serde(default)]
    pub auto_plan_classifier: Option<String>,
    #[serde(default = "default_token_mode")]
    pub token_mode: String,
}

fn default_auto_plan() -> String {
    "off".to_string()
}

fn default_token_mode() -> String {
    "full".to_string()
}

impl Default for AgentConfig {
    fn default() -> Self {
        Self {
            max_steps: default_max_steps(),
            planner_model: Some("deepseek-v4-pro".to_string()),
            executor_model: Some("deepseek-v4-flash".to_string()),
            planner_max_steps: default_planner_max_steps(),
            compact_ratio: default_compact_ratio(),
            enable_planner: false,
            auto_plan: default_auto_plan(),
            auto_plan_classifier: None,
            token_mode: default_token_mode(),
        }
    }
}

fn default_max_steps() -> u32 {
    0
}

fn default_planner_max_steps() -> u32 {
    10
}

fn default_compact_ratio() -> f32 {
    0.8
}

impl ServerConfig {
    fn resolve_api_token(&mut self) {
        if self.api_token.is_none() {
            self.api_token = std::env::var("LIKECODEX_API_TOKEN").ok();
        }
    }
}

impl Config {
    /// Return a copy of the config with secrets redacted for external APIs.
    pub fn redacted(&self) -> Config {
        let mut cfg = self.clone();
        if cfg.llm.api_key.is_some() {
            cfg.llm.api_key = Some("***".to_string());
        }
        if cfg.server.api_token.is_some() {
            cfg.server.api_token = Some("***".to_string());
        }
        cfg
    }
}
