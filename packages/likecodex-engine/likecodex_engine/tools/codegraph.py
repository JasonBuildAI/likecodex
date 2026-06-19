"""A lightweight, dependency-free code graph.

This builds a symbol table (definitions) and a call/reference graph across the
workspace using language-aware regular expressions. It is not a full parser, but
it gives the agent fast "where is X defined" and "who calls X" answers without an
embedding service or external LSP, and it caches to ``.likecodex/codegraph.json``
so repeat queries are cheap.

Supported languages: Python, JavaScript/TypeScript, Go, Rust, Java, C/C++.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from likecodex_engine.tools.encoding import read_text_detect

_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".next", "target", "dist", "build"}

_LANG_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
}

# Definition patterns per language. Each yields the symbol name in group 1 and a
# coarse kind.
_DEF_PATTERNS: dict[str, list[tuple[re.Pattern[str], str]]] = {
    "python": [
        (re.compile(r"^\s*def\s+([A-Za-z_]\w*)\s*\("), "function"),
        (re.compile(r"^\s*class\s+([A-Za-z_]\w*)"), "class"),
    ],
    "javascript": [
        (re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"), "function"),
        (re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)"), "class"),
        (re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\("), "function"),
    ],
    "typescript": [
        (re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"), "function"),
        (re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)"), "class"),
        (re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)"), "interface"),
        (re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z_$][\w$]*)"), "type"),
        (re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*[:=]"), "const"),
    ],
    "go": [
        (re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\("), "function"),
        (re.compile(r"^\s*type\s+([A-Za-z_]\w*)\s+struct"), "struct"),
        (re.compile(r"^\s*type\s+([A-Za-z_]\w*)\s+interface"), "interface"),
    ],
    "rust": [
        (re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)"), "function"),
        (re.compile(r"^\s*(?:pub\s+)?struct\s+([A-Za-z_]\w*)"), "struct"),
        (re.compile(r"^\s*(?:pub\s+)?enum\s+([A-Za-z_]\w*)"), "enum"),
        (re.compile(r"^\s*(?:pub\s+)?trait\s+([A-Za-z_]\w*)"), "trait"),
    ],
    "java": [
        (re.compile(r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?class\s+([A-Za-z_]\w*)"), "class"),
        (re.compile(r"^\s*(?:public|private|protected)?\s*interface\s+([A-Za-z_]\w*)"), "interface"),
    ],
    "c": [
        (re.compile(r"^\s*(?:[A-Za-z_][\w*\s]+?)\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{?\s*$"), "function"),
        (re.compile(r"^\s*struct\s+([A-Za-z_]\w*)"), "struct"),
    ],
    "cpp": [
        (re.compile(r"^\s*(?:[A-Za-z_][\w:*<>\s]+?)\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{?\s*$"), "function"),
        (re.compile(r"^\s*(?:class|struct)\s+([A-Za-z_]\w*)"), "class"),
    ],
}

_CALL_RE = re.compile(r"\b([A-Za-z_][\w]*)\s*\(")
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")


@dataclass
class Symbol:
    name: str
    kind: str
    path: str
    line: int


@dataclass
class CodeGraph:
    symbols: list[Symbol] = field(default_factory=list)
    # name -> list of "path:line" reference sites
    references: dict[str, list[str]] = field(default_factory=dict)
    root: str = ""
    built_at: float = 0.0
    file_count: int = 0

    def to_dict(self) -> dict:
        return {
            "symbols": [asdict(s) for s in self.symbols],
            "references": self.references,
            "root": self.root,
            "built_at": self.built_at,
            "file_count": self.file_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CodeGraph:
        graph = cls()
        graph.symbols = [Symbol(**s) for s in data.get("symbols", [])]
        graph.references = data.get("references", {})
        graph.root = data.get("root", "")
        graph.built_at = data.get("built_at", 0.0)
        graph.file_count = data.get("file_count", 0)
        return graph


def _cache_path(root: Path) -> Path:
    return root / ".likecodex" / "codegraph.json"


def _should_skip(root: Path, path: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in _SKIP_DIRS for part in parts)


def build_codegraph(root: str | Path, max_files: int = 5000) -> CodeGraph:
    """Walk the workspace and build a fresh code graph."""
    root_path = Path(root).resolve()
    graph = CodeGraph(root=str(root_path), built_at=time.time())
    defined_names: set[str] = set()

    files: list[Path] = []
    for path in root_path.rglob("*"):
        if not path.is_file() or _should_skip(root_path, path):
            continue
        if path.suffix.lower() in _LANG_BY_EXT:
            files.append(path)
        if len(files) >= max_files:
            break

    for path in files:
        lang = _LANG_BY_EXT.get(path.suffix.lower())
        if not lang:
            continue
        try:
            text = read_text_detect(path).text
        except OSError:
            continue
        rel = str(path.relative_to(root_path))
        patterns = _DEF_PATTERNS.get(lang, [])
        for idx, line in enumerate(text.splitlines(), start=1):
            for pattern, kind in patterns:
                m = pattern.match(line)
                if m:
                    name = m.group(1)
                    graph.symbols.append(Symbol(name=name, kind=kind, path=rel, line=idx))
                    defined_names.add(name)
                    break

    # Second pass: record call/reference sites for known symbols only, so the
    # graph stays small and meaningful.
    for path in files:
        try:
            text = read_text_detect(path).text
        except OSError:
            continue
        rel = str(path.relative_to(root_path))
        for idx, line in enumerate(text.splitlines(), start=1):
            for call in _CALL_RE.findall(line):
                if call in defined_names:
                    graph.references.setdefault(call, []).append(f"{rel}:{idx}")

    graph.file_count = len(files)
    return graph


def load_or_build(root: str | Path, max_age_secs: float = 3600.0) -> CodeGraph:
    """Load a cached graph if fresh, otherwise rebuild and persist it."""
    root_path = Path(root).resolve()
    cache = _cache_path(root_path)
    if cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            graph = CodeGraph.from_dict(data)
            if graph.root == str(root_path) and (time.time() - graph.built_at) < max_age_secs:
                return graph
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    graph = build_codegraph(root_path)
    save_codegraph(graph)
    return graph


def save_codegraph(graph: CodeGraph) -> None:
    cache = _cache_path(Path(graph.root))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(graph.to_dict()), encoding="utf-8")
