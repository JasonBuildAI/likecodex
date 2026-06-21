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


@dataclass
class Rule:
    tool: str
    specifier: str | None = None

    @classmethod
    def parse(cls, text: str) -> Rule:
        text = text.strip()
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\((.+)\)$", text)
        if m:
            return cls(tool=m.group(1), specifier=m.group(2))
        return cls(tool=text)

    def matches(self, tool_name: str, subject: str | None) -> bool:
        family = self._tool_family(tool_name)
        if self.tool.lower() not in {tool_name.lower(), family.lower()}:
            return False
        if self.specifier is None:
            return True
        if subject is None:
            return False
        spec = self.specifier
        if spec.endswith(":*"):
            prefix = spec[:-2]
            return subject.startswith(prefix) and "&&" not in subject and "||" not in subject
        return fnmatch.fnmatch(subject, spec)

    @staticmethod
    def _tool_family(tool_name: str) -> str:
        if tool_name == "run_command":
            return "Bash"
        if tool_name in WRITE_TOOLS:
            return "Edit"
        return tool_name


def extract_subject(tool_name: str, arguments: dict[str, Any]) -> str | None:
    if tool_name == "run_command":
        return str(arguments.get("command", ""))
    for key in ("path", "file_path", "pattern"):
        if key in arguments:
            return str(arguments[key])
    return None


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
        mode = Decision.ASK if mode_raw == "ask" else Decision.ALLOW if mode_raw == "allow" else Decision.DENY
        return cls(
            mode=mode,
            allow=[Rule.parse(r) for r in perms.get("allow", [])],
            ask=[Rule.parse(r) for r in perms.get("ask", [])],
            deny=[Rule.parse(r) for r in perms.get("deny", [])],
        )

    def decide(self, tool_name: str, read_only: bool, arguments: dict[str, Any]) -> Decision:
        subject = extract_subject(tool_name, arguments)
        grant_key = f"{tool_name}:{subject}"
        if grant_key in self.session_grants:
            return Decision.ALLOW
        if tool_name in WRITE_TOOLS and subject:
            if f"Edit:{subject}" in self.session_grants or "Edit:*" in self.session_grants:
                return Decision.ALLOW
        for rule in self.deny:
            if rule.matches(tool_name, subject):
                return Decision.DENY
        for rule in self.ask:
            if rule.matches(tool_name, subject):
                return Decision.ASK
        for rule in self.allow:
            if rule.matches(tool_name, subject):
                return Decision.ALLOW
        if read_only:
            return Decision.ALLOW
        return self.mode

    def grant_session(self, tool_name: str, subject: str | None, scope: str = "once") -> None:
        if scope == "session" and tool_name in WRITE_TOOLS:
            if subject:
                self.session_grants.add(f"Edit:{subject}")
            else:
                self.session_grants.add(f"Edit:*")
            return
        if scope == "prefix" and tool_name == "run_command" and subject:
            prefix = subject.split()[0] if subject else subject
            self.session_grants.add(f"Bash({prefix}:*)")
            return
        self.session_grants.add(f"{tool_name}:{subject}")

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
        path.write_text(json.dumps({"grants": sorted(self.session_grants)}, indent=2), encoding="utf-8")
