"""Batch code refactoring tools for the agent.

Provides:
- refactor_rename: Rename a symbol across files using regex/LSP-based replacement
- refactor_extract: Extract code block to a new function/method
- refactor_move_to_file: Move a symbol to a different file
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


class RefactorTools:
    """Batch code refactoring helpers for rename/extract/move operations."""

    def __init__(self, working_dir: str) -> None:
        self.working_dir = Path(working_dir).resolve()

    def _resolve(self, path: str) -> Path:
        target = Path(path)
        if not target.is_absolute():
            target = self.working_dir / target
        return target.resolve()

    # ----------------------------------------------------------------
    # refactor_rename
    # ----------------------------------------------------------------

    def refactor_rename_schema(self) -> dict[str, Any]:
        return {
            "description": "Rename a symbol (variable, function, class) across multiple files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_name": {"type": "string", "description": "The current name of the symbol"},
                    "new_name": {"type": "string", "description": "The new name for the symbol"},
                    "file_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Glob patterns for files to search (e.g., ['**/*.py', 'src/**/*.ts'])",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, only show matches without modifying files",
                        "default": True,
                    },
                },
                "required": ["old_name", "new_name"],
            },
        }

    async def refactor_rename(
        self,
        old_name: str,
        new_name: str,
        file_patterns: list[str] | None = None,
        dry_run: bool = True,
    ) -> str:
        """Rename a symbol across files matching the given patterns."""
        if file_patterns is None:
            file_patterns = ["**/*.py", "**/*.js", "**/*.ts", "**/*.tsx", "**/*.jsx"]

        # Build word-boundary regex for the old name
        try:
            pattern = re.compile(rf"\b{re.escape(old_name)}\b")
        except re.error as exc:
            return f"Invalid regex pattern: {exc}"

        matches: list[dict] = []
        searched_files = 0

        for glob_pattern in file_patterns:
            for file_path in self.working_dir.glob(glob_pattern):
                if not file_path.is_file():
                    continue
                searched_files += 1
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                except (OSError, UnicodeDecodeError):
                    continue

                # Find all matches with line numbers
                for match in pattern.finditer(content):
                    line_num = content[: match.start()].count("\n") + 1
                    line_start = content.rfind("\n", 0, match.start()) + 1
                    line_end = content.find("\n", match.end())
                    if line_end == -1:
                        line_end = len(content)
                    context_line = content[line_start:line_end].strip()
                    matches.append({
                        "file": str(file_path.relative_to(self.working_dir)),
                        "line": line_num,
                        "context": context_line,
                    })

        if not matches:
            return f"No matches found for '{old_name}' in {searched_files} files."

        if dry_run:
            result_lines = [
                f"Found {len(matches)} occurrences of '{old_name}' in {searched_files} files:"
            ]
            for m in matches[:50]:
                result_lines.append(f"  {m['file']}:{m['line']}: {m['context']}")
            if len(matches) > 50:
                result_lines.append(f"  ... and {len(matches) - 50} more")
            result_lines.append(f"\nTo apply, re-run with dry_run=False")
            return "\n".join(result_lines)

        # Apply rename
        modified_count = 0
        total_replacements = 0
        for glob_pattern in file_patterns:
            for file_path in self.working_dir.glob(glob_pattern):
                if not file_path.is_file():
                    continue
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                except (OSError, UnicodeDecodeError):
                    continue

                new_content = pattern.sub(new_name, content)
                if new_content != content:
                    file_path.write_text(new_content, encoding="utf-8")
                    modified_count += 1
                    total_replacements += len(pattern.findall(content))

        return (
            f"Renamed '{old_name}' to '{new_name}': "
            f"{total_replacements} replacements in {modified_count} files."
        )

    # ----------------------------------------------------------------
    # refactor_extract
    # ----------------------------------------------------------------

    def refactor_extract_schema(self) -> dict[str, Any]:
        return {
            "description": "Extract a code block from a file into a new function/method.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to extract from"},
                    "start_line": {
                        "type": "integer",
                        "description": "Start line number (1-based, inclusive)",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "End line number (1-based, inclusive)",
                    },
                    "new_function_name": {
                        "type": "string",
                        "description": "Name for the extracted function/method",
                    },
                    "insert_after_line": {
                        "type": "integer",
                        "description": "Line number after which to insert the new function (0 = top of file)",
                        "default": 0,
                    },
                    "language": {
                        "type": "string",
                        "description": "Language hint for extraction (e.g., 'python', 'typescript')",
                        "default": "auto",
                    },
                },
                "required": ["path", "start_line", "end_line", "new_function_name"],
            },
        }

    async def refactor_extract(
        self,
        path: str,
        start_line: int,
        end_line: int,
        new_function_name: str,
        insert_after_line: int = 0,
        language: str = "auto",
    ) -> str:
        """Extract a code block into a new function/method."""
        full_path = self._resolve(path)

        if not full_path.exists():
            return f"File not found: {path}"
        if not full_path.is_file():
            return f"Not a file: {path}"

        try:
            lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        except OSError as exc:
            return f"Error reading file: {exc}"

        if start_line < 1 or start_line > len(lines):
            return f"start_line {start_line} out of range (1-{len(lines)})"
        if end_line < start_line or end_line > len(lines):
            return f"end_line {end_line} out of range ({start_line}-{len(lines)})"

        # Detect indentation from the extracted block
        extracted_lines = lines[start_line - 1 : end_line]
        base_indent = ""
        for line in extracted_lines:
            if line.strip():
                base_indent = line[: len(line) - len(line.lstrip())]
                break

        # Guess language if auto
        ext = full_path.suffix.lower()
        if language == "auto":
            lang_map = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".tsx": "typescript",
                ".jsx": "javascript",
                ".go": "go",
                ".rs": "rust",
                ".java": "java",
            }
            language = lang_map.get(ext, "unknown")

        # Build function signature template
        if language == "python":
            func_template = f"\n\n{base_indent}def {new_function_name}():\n{base_indent}    pass"
        elif language in ("typescript", "javascript"):
            func_template = f"\n\n{base_indent}function {new_function_name}(): void {{\n{base_indent}    // TODO: implement\n{base_indent}}}"
        else:
            func_template = f"\n\n{base_indent}def {new_function_name}():\n{base_indent}    pass"

        # Insert the extracted code into the new function
        dedented_lines = []
        for line in extracted_lines:
            if line.startswith(base_indent) and line.strip():
                dedented = line[len(base_indent) :]
            else:
                dedented = line
            dedented_lines.append(f"{base_indent}    {dedented}" if dedented.strip() else line)

        extracted_body = "".join(dedented_lines)

        if language == "python":
            new_function = f"\n\n{base_indent}def {new_function_name}():\n{extracted_body}"
        elif language in ("typescript", "javascript"):
            new_function = f"\n\n{base_indent}function {new_function_name}(): void {{\n{extracted_body}{base_indent}}}"
        else:
            new_function = f"\n\n{base_indent}def {new_function_name}():\n{extracted_body}"

        # Replace original code with function call, insert function definition
        call_line = f"{base_indent}{new_function_name}()\n"
        if language in ("typescript", "javascript"):
            call_line = f"{base_indent}{new_function_name}();\n"

        new_lines = list(lines)
        # Replace the extracted block with the function call
        new_lines[start_line - 1 : end_line] = [call_line]

        # Insert the new function after insert_after_line
        if insert_after_line == 0:
            insert_pos = 0
        else:
            insert_pos = min(insert_after_line, len(new_lines))

        new_lines.insert(insert_pos, new_function)

        try:
            full_path.write_text("".join(new_lines), encoding="utf-8")
        except OSError as exc:
            return f"Error writing file: {exc}"

        return (
            f"Extracted lines {start_line}-{end_line} from {path} into function '{new_function_name}'. "
            f"Inserted at line {insert_pos + 1}."
        )

    # ----------------------------------------------------------------
    # refactor_move_to_file
    # ----------------------------------------------------------------

    def refactor_move_to_file_schema(self) -> dict[str, Any]:
        return {
            "description": "Move a symbol (class, function, variable) to a different file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_path": {
                        "type": "string",
                        "description": "Source file path containing the symbol",
                    },
                    "symbol_name": {
                        "type": "string",
                        "description": "Name of the symbol to move",
                    },
                    "target_path": {
                        "type": "string",
                        "description": "Target file path to move the symbol to",
                    },
                    "add_import": {
                        "type": "boolean",
                        "description": "Whether to add an import statement in the source file",
                        "default": True,
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, show what would be moved without modifying files",
                        "default": True,
                    },
                },
                "required": ["source_path", "symbol_name", "target_path"],
            },
        }

    async def refactor_move_to_file(
        self,
        source_path: str,
        symbol_name: str,
        target_path: str,
        add_import: bool = True,
        dry_run: bool = True,
    ) -> str:
        """Move a symbol to a different file."""
        source_full = self._resolve(source_path)
        target_full = self._resolve(target_path)

        if not source_full.exists():
            return f"Source file not found: {source_path}"

        try:
            source_content = source_full.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"Error reading source file: {exc}"

        # Find symbol definition using simple pattern matching
        symbol_patterns = [
            re.compile(rf"^(class\s+{re.escape(symbol_name)}\b.*)$", re.MULTILINE),
            re.compile(rf"^(def\s+{re.escape(symbol_name)}\b.*)$", re.MULTILINE),
            re.compile(rf"^(async\s+def\s+{re.escape(symbol_name)}\b.*)$", re.MULTILINE),
            re.compile(rf"^({re.escape(symbol_name)}\s*=\s*.*)$", re.MULTILINE),
            re.compile(rf"^(export\s+(default\s+)?(function|class|const|let|var)\s+{re.escape(symbol_name)}\b.*)$", re.MULTILINE),
        ]

        symbol_match = None
        symbol_start = 0
        for pat in symbol_patterns:
            m = pat.search(source_content)
            if m:
                symbol_match = m
                symbol_start = m.start()
                break

        if not symbol_match:
            return f"Symbol '{symbol_name}' not found in {source_path}"

        # Find the end of the symbol (until next top-level definition or end of file)
        remaining = source_content[symbol_start + len(symbol_match.group(0)) :]
        next_def = re.search(
            r"^(class\s+|def\s+|async\s+def\s+|@|\n\n)", remaining, re.MULTILINE
        )
        if next_def:
            symbol_end = symbol_start + len(symbol_match.group(0)) + next_def.start()
        else:
            symbol_end = len(source_content)

        symbol_code = source_content[symbol_start:symbol_end].rstrip()

        if dry_run:
            return (
                f"Would move symbol '{symbol_name}' from {source_path} to {target_path}.\n"
                f"Symbol code:\n```\n{symbol_code}\n```\n"
                f"Add import in source: {add_import}\n"
                f"To apply, re-run with dry_run=False"
            )

        # Build target content
        if target_full.exists():
            target_content = target_full.read_text(encoding="utf-8", errors="replace")
            # Add blank line separator before appending
            if not target_content.endswith("\n"):
                target_content += "\n"
            target_content += f"\n{symbol_code}\n"
        else:
            target_content = f"{symbol_code}\n"

        # Remove symbol from source
        new_source = source_content[:symbol_start] + source_content[symbol_end:].lstrip("\n")

        # Add import statement in source if requested
        if add_import:
            rel_path = os.path.relpath(
                target_full, source_full.parent
            ).replace("\\", "/")
            if rel_path.endswith(".py"):
                import_module = rel_path[:-3].replace("/", ".")
            elif rel_path.endswith((".ts", ".tsx", ".js", ".jsx")):
                import_module = rel_path.rsplit(".", 1)[0]
                # For JS/TS, use import statement
                import_stmt = f"import {{ {symbol_name} }} from './{import_module}';\n"
                new_source = import_stmt + new_source
            else:
                import_module = rel_path.rsplit(".", 1)[0]
                import_stmt = f"from {import_module} import {symbol_name}\n"
                new_source = import_stmt + new_source

        # Write both files
        try:
            source_full.write_text(new_source, encoding="utf-8")
            target_full.parent.mkdir(parents=True, exist_ok=True)
            target_full.write_text(target_content, encoding="utf-8")
        except OSError as exc:
            return f"Error writing files: {exc}"

        return (
            f"Moved symbol '{symbol_name}' from {source_path} to {target_path}. "
            f"{'Added import in source.' if add_import else ''}"
        )
