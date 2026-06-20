"""Static code review tools for the agent."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class CodeReviewTools:
    """Best-effort static review helpers: pattern-based bug/quality checks."""

    def __init__(self, working_dir: str) -> None:
        self.working_dir = Path(working_dir).resolve()

    def _resolve(self, path: str) -> Path:
        target = Path(path)
        if not target.is_absolute():
            target = self.working_dir / target
        return target.resolve()

    def review_file_schema(self) -> dict[str, Any]:
        return {
            "description": "Review a source file for common issues, bugs, and style problems.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative or absolute file path"},
                    "focus": {
                        "type": "string",
                        "enum": ["general", "security", "performance", "style"],
                        "default": "general",
                    },
                },
                "required": ["path"],
            },
        }

    async def review_file(self, path: str, focus: str = "general") -> str:
        target = self._resolve(path)
        if not target.exists():
            return json.dumps({"error": f"File not found: {path}"})
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return json.dumps({"error": str(e)})

        findings = []
        lines = content.splitlines()
        ext = target.suffix.lower()

        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            if focus in ("general", "security"):
                keywords = ["password", "secret", "token", "api_key"]
                has_secret_keyword = self._match_any(stripped, keywords)
                looks_like_assignment = "=" in stripped
                not_from_env = "getenv" not in stripped
                not_from_config = "config" not in stripped.lower()
                if has_secret_keyword and looks_like_assignment and not_from_env and not_from_config:
                    findings.append(self._finding(i, "warning", "security", "Possible hardcoded secret"))
                if "eval(" in stripped or "exec(" in stripped:
                    msg = "Dangerous eval/exec usage"
                    findings.append(self._finding(i, "error", "security", msg))
                if "TODO" in stripped or "FIXME" in stripped:
                    findings.append(self._finding(i, "info", "style", "Unresolved TODO/FIXME"))
            if focus in ("general", "performance"):
                if ext == ".py" and re.search(r"for\s+\w+\s+in\s+range\s*\(\s*len\s*\(", line):
                    msg = "Consider iterating collection directly"
                    findings.append(self._finding(i, "warning", "performance", msg))
                if re.search(r"\+\s*['\"]", line) and ext in (".py", ".js", ".ts"):
                    msg = "Consider using f-string/template for concatenation"
                    findings.append(self._finding(i, "info", "performance", msg))
            if focus in ("general", "style"):
                if line.endswith(" ") or line.endswith("\t"):
                    findings.append(self._finding(i, "info", "style", "Trailing whitespace"))
                if len(line) > 120:
                    findings.append(self._finding(i, "info", "style", "Line exceeds 120 characters"))

        summary = {
            "path": str(target),
            "focus": focus,
            "total_lines": len(lines),
            "findings": findings,
            "issue_counts": self._count_findings(findings),
        }
        return json.dumps(summary)

    def review_diff_schema(self) -> dict[str, Any]:
        return {
            "description": "Review a git diff or patch string for potential issues.",
            "parameters": {
                "type": "object",
                "properties": {
                    "diff": {"type": "string", "description": "Diff content to review"},
                },
                "required": ["diff"],
            },
        }

    async def review_diff(self, diff: str) -> str:
        findings = []
        current_file: str | None = None
        for i, line in enumerate(diff.splitlines(), start=1):
            if line.startswith("diff --git"):
                parts = line.split()
                current_file = parts[-1] if len(parts) >= 3 else None
            if line.startswith("+") and not line.startswith("+++"):
                content = line[1:]
                if "TODO" in content or "FIXME" in content:
                    msg = "New TODO/FIXME"
                    findings.append(self._finding(i, "info", "style", msg, current_file))
                if re.search(r"console\.log|print\(|debugger;|breakpoint\(", content):
                    msg = "Debug print/statement added"
                    findings.append(self._finding(i, "warning", "style", msg, current_file))
                if "eval(" in content or "exec(" in content:
                    msg = "Dangerous eval/exec added"
                    findings.append(self._finding(i, "error", "security", msg, current_file))
        return json.dumps({"findings": findings, "issue_counts": self._count_findings(findings)})

    def check_dependencies_schema(self) -> dict[str, Any]:
        desc = "Check dependency manifest files for common issues."
        manifest_desc = "Path to requirements.txt, package.json, Cargo.toml, or pyproject.toml"
        return {
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": {
                    "manifest": {"type": "string", "description": manifest_desc},
                },
                "required": ["manifest"],
            },
        }

    async def check_dependencies(self, manifest: str) -> str:
        target = self._resolve(manifest)
        if not target.exists():
            return json.dumps({"error": f"Manifest not found: {manifest}"})
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return json.dumps({"error": str(e)})

        findings = []
        name = target.name.lower()
        if name == "requirements.txt":
            for i, line in enumerate(content.splitlines(), start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                pinned = "==" in stripped or ">=" in stripped or "~=" in stripped
                if not pinned:
                    msg = "Dependency lacks pinned version"
                    findings.append(self._finding(i, "warning", "dependencies", msg))
        elif name == "package.json":
            if '"^' in content or '"~' in content:
                msg = "Semver prefixes present; consider lockfile for reproducibility"
                findings.append(self._finding(0, "info", "dependencies", msg))
        elif name == "cargo.toml":
            if "*" in content:
                msg = "Wildcard dependency version detected"
                findings.append(self._finding(0, "warning", "dependencies", msg))
        elif name == "pyproject.toml":
            has_deps = "dependencies = [" in content or "[project.dependencies]" in content
            if has_deps and "==" not in content:
                msg = "Project dependencies may not be pinned"
                findings.append(self._finding(0, "info", "dependencies", msg))

        return json.dumps({"manifest": str(target), "findings": findings})

    @staticmethod
    def _finding(
        line: int,
        severity: str,
        category: str,
        message: str,
        file: str | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "line": line,
            "severity": severity,
            "category": category,
            "message": message,
        }
        if file is not None:
            result["file"] = file
        return result

    @staticmethod
    def _match_any(text: str, keywords: list[str]) -> bool:
        lowered = text.lower()
        return any(kw in lowered for kw in keywords)

    @staticmethod
    def _count_findings(findings: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in findings:
            sev = item.get("severity", "info")
            counts[sev] = counts.get(sev, 0) + 1
        return counts
