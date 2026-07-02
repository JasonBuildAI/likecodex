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

    SECURITY_PATTERNS = [
        (r"eval\(.*\)", "Avoid eval() - can execute arbitrary code"),
        (r"exec\(.*\)", "Avoid exec() - can execute arbitrary code"),
        (r"subprocess\.call\(.*shell=True.*\)", "shell=True allows command injection"),
        (r"os\.system\(", "os.system() allows command injection"),
        (r"pickle\.loads?", "Unsafe deserialization with pickle"),
        (r"yaml\.load\(.*\)(?!.*Loader)", "Unsafe YAML deserialization - use yaml.safe_load"),
        (r"marshal\.loads?", "Unsafe deserialization with marshal"),
        (r"shelve\.open", "Unsafe deserialization with shelve"),
        (r"Markup\(.*\)|mark_safe\(", "Potential XSS vulnerability - escaping disabled"),
        (r"paramiko\.connect\(.*password=", "Hardcoded SSH password"),
        (r"hashlib\.md5\b|hashlib\.sha1\b", "Weak hashing algorithm - use SHA-256 or higher"),
        (r"jwt\.encode\(.*algorithm=(none|None)", "JWT with 'none' algorithm is insecure"),
    ]

    PERFORMANCE_PATTERNS = [
        (r"for\s+\w+\s+in\s+range\s*\(\s*len\s*\(", "Consider iterating collection directly instead of range(len())"),
        (r"\.append\(.*\),?\s*\n\s*\.append\(", "Multiple appends can be replaced with .extend()"),
        (r"time\.sleep\(.*\)", "time.sleep() blocks event loop - use asyncio.sleep"),
        (r"for.*in.*\.iterrows\(\)", "pandas iterrows() is slow - use vectorized operations"),
        (r"while\s+True\s*:", "Infinite loop detected - ensure there is a break condition"),
        (r"global\s+", "Avoid global variables in performance-critical code"),
    ]

    STYLE_PATTERNS = [
        (r"import\s+\*", "Wildcard imports are discouraged"),
        (r"#\s*TODO", "Unresolved TODO comment"),
        (r"#\s*FIXME", "Unresolved FIXME comment"),
        (r"^\s*print\(", "Consider using logging instead of print()"),
    ]

    def review_file_schema(self) -> dict[str, Any]:
        return {
            "description": "Review a source file for common issues, bugs, style problems, and security vulnerabilities.",
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

        # ---- Security checks ----
        if focus in ("general", "security"):
            for i, line in enumerate(lines, start=1):
                stripped = line.strip()
                keywords = ["password", "secret", "token", "api_key"]
                has_secret_keyword = self._match_any(stripped, keywords)
                looks_like_assignment = "=" in stripped
                not_from_env = "getenv" not in stripped
                not_from_config = "config" not in stripped.lower()
                if has_secret_keyword and looks_like_assignment and not_from_env and not_from_config:
                    findings.append(self._finding(i, "warning", "security", "Possible hardcoded secret"))

            for pat, msg in self.SECURITY_PATTERNS:
                for match in re.finditer(pat, content, re.MULTILINE):
                    line_no = content[:match.start()].count("\n") + 1
                    findings.append(self._finding(line_no, "error", "security", msg))
                    if len(findings) >= 50:
                        break
                if len(findings) >= 50:
                    break

        # ---- Performance checks ----
        if focus in ("general", "performance"):
            for pat, msg in self.PERFORMANCE_PATTERNS:
                for match in re.finditer(pat, content):
                    line_no = content[:match.start()].count("\n") + 1
                    findings.append(self._finding(line_no, "warning", "performance", msg))
                    if len(findings) >= 50:
                        break
                if len(findings) >= 50:
                    break

            for i, line in enumerate(lines, start=1):
                if ext == ".py" and re.search(r"for\s+\w+\s+in\s+range\s*\(\s*len\s*\(", line):
                    findings.append(self._finding(i, "warning", "performance", "Consider iterating collection directly"))
                concat_pattern = "\\+\\s*['\"]"
                if re.search(concat_pattern, line) and ext in (".py", ".js", ".ts"):
                    findings.append(self._finding(i, "info", "performance", "Consider using f-string/template for concatenation"))

        # ---- Style checks ----
        if focus in ("general", "style"):
            for pat, msg in self.STYLE_PATTERNS:
                for match in re.finditer(pat, content, re.MULTILINE):
                    line_no = content[:match.start()].count("\n") + 1
                    findings.append(self._finding(line_no, "info", "style", msg))
                    if len(findings) >= 50:
                        break
                if len(findings) >= 50:
                    break

            for i, line in enumerate(lines, start=1):
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
                for pat, pat_msg in self.SECURITY_PATTERNS:
                    if re.search(pat, content):
                        findings.append(
                            self._finding(i, "error", "security", f"[Added] {pat_msg}", current_file)
                        )
                        break
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

    def review_workspace_schema(self) -> dict[str, Any]:
        return {
            "description": "Review multiple files matching a glob pattern in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "glob": {"type": "string", "description": "Glob pattern, e.g. 'src/**/*.py'"},
                    "focus": {
                        "type": "string",
                        "enum": ["general", "security", "performance", "style"],
                        "default": "general",
                    },
                    "max_files": {"type": "integer", "default": 20},
                },
                "required": ["glob"],
            },
        }

    async def review_workspace(self, glob: str, focus: str = "general", max_files: int = 20) -> str:
        """Review multiple files matching a glob pattern."""
        if "*" in glob and "**" not in glob and "/" not in glob:
            glob = f"**/{glob}"
        file_results = []
        total_findings = 0
        for entry in self.working_dir.glob(glob):
            if not entry.is_file():
                continue
            rel = entry.relative_to(self.working_dir)
            result = await self.review_file(str(rel), focus)
            data = json.loads(result)
            if "error" in data:
                continue
            if data.get("findings"):
                file_results.append({
                    "path": str(rel),
                    "findings": data["findings"],
                    "issue_counts": data["issue_counts"],
                })
                total_findings += len(data["findings"])
            if len(file_results) >= max_files:
                break
        return json.dumps({
            "files_reviewed": len(file_results),
            "total_findings": total_findings,
            "results": file_results,
        })

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
