"""Policy rules for fine-grained tool permissions."""

from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class Decision(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


WRITE_TOOLS = frozenset(
    {
        "write_file",
        "edit_file",
        "multi_edit",
        "move_file",
        "delete_range",
        "delete_symbol",
        "notebook_edit",
        "git_commit",
    }
)

# Tool families for grouped permission rules
TOOL_FAMILIES: dict[str, str] = {
    "run_command": "Bash",
    "write_file": "Edit",
    "edit_file": "Edit",
    "multi_edit": "Edit",
    "move_file": "Edit",
    "delete_range": "Edit",
    "delete_symbol": "Edit",
    "notebook_edit": "Edit",
    "git_commit": "Edit",
    "read_file": "Read",
    "list_dir": "Read",
    "ls": "Read",
    "glob": "Read",
    "search_files": "Read",
    "grep_files": "Read",
    "git_status": "Read",
    "git_diff": "Read",
    "git_log": "Read",
    "git_branch": "Read",
    "web_fetch": "Web",
    "web_search": "Web",
}


@dataclass
class Rule:
    """A permission rule matching tool calls by name and optional subject pattern.

    Supports:
    - Exact tool name: "run_command"
    - Family name: "Bash", "Edit", "Read", "Web"
    - With glob specifier: "Bash(go test:*)", "Edit(docs/**)"
    - With literal specifier: "Bash=go test ./..."
    - With fnmatch specifier: "Edit(*.py)"
    """

    tool: str
    specifier: str | None = None

    @classmethod
    def parse(cls, text: str) -> Rule:
        text = text.strip()
        # Try parenthesized format: ToolName(specifier)
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\((.+)\)$", text)
        if m:
            return cls(tool=m.group(1), specifier=m.group(2))
        # Try equals format: ToolName=literal
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.+)$", text)
        if m:
            return cls(tool=m.group(1), specifier=f"={m.group(2)}")
        return cls(tool=text)

    def matches(self, tool_name: str, subject: str | None) -> bool:
        family = self._tool_family(tool_name)
        # Check if the rule's tool name matches either the tool name or its family
        rule_lower = self.tool.lower()
        if rule_lower not in {tool_name.lower(), family.lower()}:
            return False
        # No specifier = match all
        if self.specifier is None:
            return True
        if subject is None:
            return False
        return self._specifier_matches(subject)

    def _specifier_matches(self, subject: str) -> bool:
        spec = self.specifier
        if spec is None:
            return True
        # Literal match: =value
        if spec.startswith("="):
            return subject == spec[1:]
        # Prefix match: prefix:*
        if spec.endswith(":*"):
            prefix = spec[:-2]
            return subject.startswith(prefix) and "&&" not in subject and "||" not in subject
        # Glob match: **/*.py, docs/** etc.
        if "*" in spec or "?" in spec or "[" in spec:
            return fnmatch.fnmatch(subject, spec)
        # Fallback: exact match
        return subject == spec

    @staticmethod
    def _tool_family(tool_name: str) -> str:
        return TOOL_FAMILIES.get(tool_name, tool_name)


def extract_subject(tool_name: str, arguments: dict[str, Any]) -> str | None:
    """Extract the primary subject from tool arguments."""
    if tool_name == "run_command":
        return str(arguments.get("command", ""))
    if tool_name in {"move_file", "multi_edit"}:
        # For move and multi_edit, use the first path/file_path
        for key in ("source_path", "path", "file_path", "source"):
            if key in arguments:
                return str(arguments[key])
    for key in ("path", "file_path", "pattern", "name"):
        if key in arguments:
            return str(arguments[key])
    return None


def extract_subjects(tool_name: str, arguments: dict[str, Any]) -> list[str]:
    """Extract all subjects from tool arguments (for multi-target tools)."""
    subjects: list[str] = []
    if tool_name == "run_command":
        cmd = str(arguments.get("command", ""))
        if cmd:
            subjects.append(cmd)
    elif tool_name == "move_file":
        for key in ("source_path", "destination_path", "source", "dest"):
            if key in arguments:
                subjects.append(str(arguments[key]))
    elif tool_name == "multi_edit":
        edits = arguments.get("edits", [])
        if isinstance(edits, list):
            for edit in edits:
                if isinstance(edit, dict):
                    for key in ("path", "file_path"):
                        if key in edit:
                            subjects.append(str(edit[key]))
    else:
        for key in ("path", "file_path", "pattern", "name"):
            if key in arguments:
                subjects.append(str(arguments[key]))
    return subjects


@dataclass
class Policy:
    mode: Decision = Decision.ASK
    allow: list[Rule] = field(default_factory=list)
    ask: list[Rule] = field(default_factory=list)
    deny: list[Rule] = field(default_factory=list)
    session_grants: set[str] = field(default_factory=set)

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> Policy:
        cfg = config or {}
        perms = cfg.get("permissions", cfg)
        mode_raw = str(perms.get("mode", "ask")).lower()
        if mode_raw == "ask":
            mode = Decision.ASK
        elif mode_raw == "allow":
            mode = Decision.ALLOW
        elif mode_raw == "deny":
            mode = Decision.DENY
        else:
            mode = Decision.ASK
        return cls(
            mode=mode,
            allow=[Rule.parse(r) for r in perms.get("allow", [])],
            ask=[Rule.parse(r) for r in perms.get("ask", [])],
            deny=[Rule.parse(r) for r in perms.get("deny", [])],
        )

    def decide(self, tool_name: str, read_only: bool, arguments: dict[str, Any]) -> Decision:
        subject = extract_subject(tool_name, arguments)
        subjects = extract_subjects(tool_name, arguments) if subject else []

        # Check session grants
        grant_key = f"{tool_name}:{subject}"
        if grant_key in self.session_grants:
            return Decision.ALLOW

        # Check family grants (Edit:*, Bash:...)
        family = TOOL_FAMILIES.get(tool_name, tool_name)
        if f"{family}:*" in self.session_grants:
            return Decision.ALLOW
        if subject and f"{family}:{subject}" in self.session_grants:
            return Decision.ALLOW

        # Check multi-subject grants
        for subj in subjects:
            if f"{tool_name}:{subj}" in self.session_grants:
                return Decision.ALLOW

        # Check deny rules
        for rule in self.deny:
            if rule.matches(tool_name, subject):
                return Decision.DENY
            # Check all subjects for multi-target tools
            for subj in subjects:
                if rule.matches(tool_name, subj):
                    return Decision.DENY

        # Check ask rules
        for rule in self.ask:
            if rule.matches(tool_name, subject):
                return Decision.ASK
            for subj in subjects:
                if rule.matches(tool_name, subj):
                    return Decision.ASK

        # Check allow rules
        for rule in self.allow:
            if rule.matches(tool_name, subject):
                return Decision.ALLOW
            for subj in subjects:
                if rule.matches(tool_name, subj):
                    return Decision.ALLOW

        if read_only:
            return Decision.ALLOW
        return self.mode

    def grant_session(self, tool_name: str, subject: str | None, scope: str = "once") -> None:
        if scope == "once":
            return  # Don't persist one-time grants

        family = TOOL_FAMILIES.get(tool_name, tool_name)

        if scope == "session":
            if subject:
                self.session_grants.add(f"{family}:{subject}")
            else:
                self.session_grants.add(f"{family}:*")
            return

        if scope == "prefix" and tool_name == "run_command" and subject:
            # Extract the base command as prefix
            prefix = subject.split()[0] if subject else subject
            self.session_grants.add(f"Bash({prefix}:*)")
            return

        if scope == "always":
            if subject:
                self.session_grants.add(f"{tool_name}:{subject}")
            else:
                self.session_grants.add(f"{family}:*")
            return

    def load_grants(self, path: Path) -> None:
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.session_grants = set(data.get("grants", []))
        except (json.JSONDecodeError, OSError):
            pass

    def save_grants(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"grants": sorted(self.session_grants)}, indent=2),
            encoding="utf-8",
        )
