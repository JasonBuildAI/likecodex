"""Bash command readonly detection and safety classification.

Detects whether a shell command is read-only or dangerous,
enabling fine-grained permission decisions for the run_command tool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import ClassVar

# Commands that are known to be read-only (no filesystem mutations).
READONLY_COMMANDS: set[str] = {
    "cat", "head", "tail", "less", "more",
    "ls", "dir", "tree",
    "grep", "rg", "ag", "ack",
    "find", "locate", "which", "whereis", "type",
    "echo", "printf",
    "date", "time", "uptime", "hostname", "uname", "whoami", "id",
    "env", "printenv", "pwd", "basename", "dirname", "realpath", "readlink",
    "wc", "sort", "uniq", "cut", "tr", "awk", "sed -n",
    "git log", "git status", "git diff", "git show", "git branch", "git tag",
    "git blame", "git stash list", "git remote", "git config",
    "docker ps", "docker images", "docker logs", "docker inspect",
    "docker stats", "docker version", "docker info",
    "kubectl get", "kubectl describe", "kubectl logs", "kubectl top",
    "npm ls", "npm list", "npm view", "npm info", "npm outdated",
    "pip list", "pip show", "pip freeze",
    "cargo check", "cargo tree", "cargo search",
    "go list", "go version", "go env",
    "python -c", "python3 -c", "node -e", "node -p",
    "rustc --version", "rustup show",
    "df", "du", "free", "ps", "top", "htop", "netstat", "ss", "lsof",
    "pgrep", "pidof", "stat", "file", "md5sum", "sha256sum", "sha1sum",
    "diff", "cmp", "comm", "jq", "yq", "xxd", "od", "hexdump",
}

# Patterns that indicate dangerous commands regardless of the base command.
DANGEROUS_PATTERNS: list[str] = [
    r"rm\s+-rf?\s",
    r"rm\s+.*\*",
    r"git\s+push\s+.*--force",
    r"git\s+push\s+.*--delete",
    r"git\s+reset\s+--hard",
    r"git\s+clean\s+-[fdx]",
    r"chmod\s+777",
    r"chmod\s+-R\s+777",
    r"chown\s+-R",
    r">\s*/dev/",
    r"mkfs\.",
    r"dd\s+if=",
    r":\(\)\s*\{",
    r"curl.*\|\s*(ba)?sh",
    r"wget.*\|\s*(ba)?sh",
    r"sudo\s+",
    r"shutdown",
    r"reboot",
    r"halt",
    r"poweroff",
    r"init\s+[0-6]",
    r"systemctl\s+(stop|disable|mask)",
    r"kill\s+-9",
    r"pkill\s+-9",
    r"docker\s+(rm|rmi|stop|kill|prune)",
    r"kubectl\s+delete",
    r"npm\s+(uninstall|rm)",
    r"pip\s+uninstall",
    r"cargo\s+uninstall",
    r"cargo\s+clean",
    r"mv\s+.*/etc/",
    r"mv\s+.*/sys/",
    r"mv\s+.*/proc/",
    r"cp\s+.*/etc/",
    r"cp\s+.*/sys/",
    r"cp\s+.*/proc/",
    r"format\s",
    r"fdisk\s",
    r"mount\s",
    r"umount\s",
    r"cryptsetup",
    r"openssl\s+genrsa",
    r"ssh-keygen",
]

# Patterns that are always safe even when combined with other commands.
SAFE_COMBINED_PATTERNS: list[str] = [
    r"^\s*(echo|printf|cat)\s+",
    r"^\s*(ls|dir|tree)\s+",
    r"^\s*(grep|rg)\s+",
    r"^\s*head\s+",
    r"^\s*tail\s+",
    r"^\s*wc\s+",
    r"^\s*(date|time|pwd|whoami|hostname|uname)",
    r"^\s*git\s+(status|diff|log|show|branch|tag|blame)",
    r"^\s*docker\s+(ps|images|logs|inspect|stats|version|info)",
    r"^\s*kubectl\s+(get|describe|logs|top)",
    r"^\s*npm\s+(ls|list|view|info|outdated)",
    r"^\s*pip\s+(list|show|freeze)",
    r"^\s*cargo\s+(check|tree|search)",
    r"^\s*go\s+(list|version|env)",
]


@dataclass
class BashClassification:
    """Result of classifying a bash command."""
    is_readonly: bool
    is_dangerous: bool
    base_command: str
    warnings: list[str] = field(default_factory=list)
    confidence: str = "high"  # "high", "medium", "low"


def extract_base_command(command: str) -> str:
    """Extract the base command from a shell command string.

    Handles: chained commands (&&, ;, |), sudo, env vars, etc.
    """
    cmd = command.strip()
    # Remove leading variable assignments
    cmd = re.sub(r'^\s*\w+=\S+\s+', '', cmd)
    # Remove leading sudo
    cmd = re.sub(r'^\s*sudo\s+', '', cmd)
    # Take first command before &&, ;, |, ||
    for sep in ['&&', '||', ';', '|']:
        if sep in cmd:
            cmd = cmd.split(sep)[0]
    # Get the first word(s) as the base command
    parts = cmd.strip().split()
    if not parts:
        return ""
    # For two-word commands like "git log", return both
    if len(parts) >= 2 and parts[0] in {"git", "docker", "kubectl", "npm", "pip", "cargo", "go"}:
        return f"{parts[0]} {parts[1]}"
    return parts[0]


def is_readonly_command(command: str) -> bool:
    """Check if a command is known to be read-only."""
    base = extract_base_command(command)
    cmd_lower = command.lower().strip()

    # Check exact match in readonly set
    if base.lower() in READONLY_COMMANDS:
        return True

    # Check safe combined patterns
    for pattern in SAFE_COMBINED_PATTERNS:
        if re.match(pattern, cmd_lower):
            return True

    # Check if the command starts with a readonly base
    for readonly_cmd in READONLY_COMMANDS:
        if cmd_lower.startswith(readonly_cmd):
            return True

    return False


def detect_dangerous_patterns(command: str) -> list[str]:
    """Detect dangerous patterns in a command and return warnings."""
    cmd_lower = command.lower().strip()
    warnings: list[str] = []

    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd_lower):
            # Generate a human-readable warning
            warning = _pattern_to_warning(pattern)
            if warning:
                warnings.append(warning)

    return warnings


def _pattern_to_warning(pattern: str) -> str:
    """Convert a regex pattern to a human-readable warning."""
    mapping = {
        r"rm\s+-rf?\s": "forceful file deletion (rm -rf)",
        r"rm\s+.*\*": "wildcard file deletion",
        r"git\s+push\s+.*--force": "force push to remote",
        r"git\s+reset\s+--hard": "hard git reset (destructive)",
        r"chmod\s+777": "overly permissive chmod 777",
        r"chmod\s+-R\s+777": "recursive chmod 777",
        r"sudo\s+": "superuser (sudo) execution",
        r"shutdown": "system shutdown",
        r"reboot": "system reboot",
        r"kill\s+-9": "force kill (SIGKILL)",
        r"docker\s+(rm|rmi|stop|kill|prune)": "destructive docker operation",
        r"kubectl\s+delete": "kubernetes resource deletion",
        r"curl.*\|\s*(ba)?sh": "curl pipe to shell (remote code execution)",
        r"wget.*\|\s*(ba)?sh": "wget pipe to shell (remote code execution)",
    }
    return mapping.get(pattern, f"dangerous pattern: {pattern}")


def classify_bash(command: str) -> BashClassification:
    """Classify a bash command as readonly, dangerous, or neutral.

    Returns a BashClassification with readonly flag, dangerous flag,
    base command, and any warnings.
    """
    base = extract_base_command(command)
    is_readonly = is_readonly_command(command)
    warnings = detect_dangerous_patterns(command)

    is_dangerous = len(warnings) > 0

    # If both readonly and dangerous, dangerous wins
    if is_dangerous:
        is_readonly = False

    # Confidence level
    if base in READONLY_COMMANDS or any(
        re.match(p, command.lower().strip()) for p in SAFE_COMBINED_PATTERNS
    ):
        confidence = "high"
    elif is_dangerous:
        confidence = "high"
    else:
        confidence = "medium"

    return BashClassification(
        is_readonly=is_readonly,
        is_dangerous=is_dangerous,
        base_command=base,
        warnings=warnings,
        confidence=confidence,
    )