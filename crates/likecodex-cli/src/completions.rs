//! Shell command completion generation.
//!
//! Generates shell completion scripts for `likecodex` CLI commands.
//! Supports Bash, Zsh, Fish, PowerShell, and Elvish.
//!
//! Usage:
//! ```shell
//! likecodex completions bash > ~/.likecodex-completions.bash
//! echo "source ~/.likecodex-completions.bash" >> ~/.bashrc
//! ```

use clap::Command;

/// Generate shell completion script for the specified shell.
///
/// Returns the completion script as a string.
pub fn generate(shell: ShellKind, cmd: &mut Command) -> String {
    use clap_complete::Generator;

    let mut buf = Vec::new();
    let gen: Box<dyn Generator> = match shell {
        ShellKind::Bash => Box::new(clap_complete::shells::Bash),
        ShellKind::Zsh => Box::new(clap_complete::shells::Zsh),
        ShellKind::Fish => Box::new(clap_complete::shells::Fish),
        ShellKind::PowerShell => Box::new(clap_complete::shells::PowerShell),
        ShellKind::Elvish => Box::new(clap_complete::shells::Elvish),
    };

    gen.generate(cmd, &mut buf);
    String::from_utf8(buf).unwrap_or_default()
}

/// Supported shell kinds for completion generation.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ShellKind {
    Bash,
    Zsh,
    Fish,
    PowerShell,
    Elvish,
}

impl ShellKind {
    /// Parse from a CLI argument string.
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "bash" => Some(ShellKind::Bash),
            "zsh" => Some(ShellKind::Zsh),
            "fish" => Some(ShellKind::Fish),
            "powershell" | "pwsh" => Some(ShellKind::PowerShell),
            "elvish" => Some(ShellKind::Elvish),
            _ => None,
        }
    }

    /// All supported shell kinds.
    pub fn all() -> Vec<Self> {
        vec![
            ShellKind::Bash,
            ShellKind::Zsh,
            ShellKind::Fish,
            ShellKind::PowerShell,
            ShellKind::Elvish,
        ]
    }

    /// Human-readable name.
    pub fn name(&self) -> &'static str {
        match self {
            ShellKind::Bash => "bash",
            ShellKind::Zsh => "zsh",
            ShellKind::Fish => "fish",
            ShellKind::PowerShell => "powershell",
            ShellKind::Elvish => "elvish",
        }
    }
}

impl std::fmt::Display for ShellKind {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.name())
    }
}

/// Path hints for installing completions on various shells.
pub fn install_hint(shell: ShellKind) -> &'static str {
    match shell {
        ShellKind::Bash => r#"Source in ~/.bashrc:
    source <(likecodex completions bash)"#,
        ShellKind::Zsh => r#"Source in ~/.zshrc:
    source <(likecodex completions zsh)"#,
        ShellKind::Fish => r#"Copy to completions directory:
    likecodex completions fish > ~/.config/fish/completions/likecodex.fish"#,
        ShellKind::PowerShell => r#"Add to PowerShell profile:
    likecodex completions powershell | Out-String | Invoke-Expression"#,
        ShellKind::Elvish => r#"Source in ~/.elvish/rc.elv:
    eval (likecodex completions elvish | slurp)"#,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use clap::{Command, Arg};

    fn test_command() -> Command {
        Command::new("likecodex")
            .about("A production-grade Codex-like coding agent")
            .subcommand(Command::new("doctor").about("Check environment"))
            .subcommand(Command::new("stats").about("Show cache stats"))
            .subcommand(
                Command::new("run")
                    .about("Run a prompt")
                    .arg(Arg::new("prompt").required(true)),
            )
    }

    #[test]
    fn test_completions_generate_bash() {
        let script = generate(ShellKind::Bash, &mut test_command());
        assert!(script.contains("likecodex"));
        assert!(script.contains("_likecodex"));
    }

    #[test]
    fn test_completions_generate_zsh() {
        let script = generate(ShellKind::Zsh, &mut test_command());
        assert!(!script.is_empty());
    }

    #[test]
    fn test_completions_generate_fish() {
        let script = generate(ShellKind::Fish, &mut test_command());
        assert!(script.contains("complete"));
    }

    #[test]
    fn test_shell_kind_parse() {
        assert_eq!(ShellKind::from_str("bash"), Some(ShellKind::Bash));
        assert_eq!(ShellKind::from_str("zsh"), Some(ShellKind::Zsh));
        assert_eq!(ShellKind::from_str("fish"), Some(ShellKind::Fish));
        assert_eq!(ShellKind::from_str("powershell"), Some(ShellKind::PowerShell));
        assert_eq!(ShellKind::from_str("pwsh"), Some(ShellKind::PowerShell));
        assert_eq!(ShellKind::from_str("elvish"), Some(ShellKind::Elvish));
        assert_eq!(ShellKind::from_str("unknown"), None);
    }

    #[test]
    fn test_install_hint_exists() {
        for shell in ShellKind::all() {
            let hint = install_hint(shell);
            assert!(!hint.is_empty(), "missing install hint for {shell}");
        }
    }
}
