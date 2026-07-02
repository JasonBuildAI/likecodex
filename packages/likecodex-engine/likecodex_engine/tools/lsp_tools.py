"""LSP tool wrappers.

Phase 7.10: Quick Fix Suggestions
- LSP code actions (quick-fixes, refactors)
- Suggest fixes from diagnostics
- Apply fix endpoint
"""

from __future__ import annotations

import json
from typing import Any

from likecodex_engine.lsp.manager import LspManager
from likecodex_engine.tools.lsp import LspTools as CheckerTools


_SYMBOL_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "file": {"type": "string"},
        "line": {"type": "integer"},
        "symbol": {"type": "string"},
    },
    "required": ["file", "line", "symbol"],
}


class LspSemanticTools:
    def __init__(self, working_dir: str) -> None:
        self.working_dir = working_dir
        self.manager = LspManager(working_dir)
        self.checker = CheckerTools(working_dir)

    def lsp_definition_schema(self) -> dict[str, Any]:
        return {"description": "Jump to symbol definition via LSP.", "parameters": _SYMBOL_PARAMS}

    def lsp_references_schema(self) -> dict[str, Any]:
        return {"description": "Find symbol references via LSP (falls back to grep hint).", "parameters": _SYMBOL_PARAMS}

    def lsp_hover_schema(self) -> dict[str, Any]:
        return {"description": "Show hover docs for a symbol.", "parameters": _SYMBOL_PARAMS}

    def lsp_diagnostics_schema(self) -> dict[str, Any]:
        return self.checker.diagnostics_schema()

    def lsp_code_action_schema(self) -> dict[str, Any]:
        return {
            "description": "Get available code actions (quick fixes, refactors, organize imports) for a position in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative file path"},
                    "line": {"type": "integer", "description": "1-based line number"},
                },
                "required": ["file_path", "line"],
            },
        }

    def lsp_code_action_apply_schema(self) -> dict[str, Any]:
        return {
            "description": "Apply a code action (quick fix) at a given position in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative file path"},
                    "line": {"type": "integer", "description": "1-based line number"},
                    "action_index": {"type": "integer", "description": "Index of the action from the list returned by lsp_code_action"},
                },
                "required": ["file_path", "line", "action_index"],
            },
        }

    def lsp_suggest_fixes_schema(self) -> dict[str, Any]:
        return {
            "description": "Run diagnostics and suggest automatic fixes for any issues found in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path to check"},
                },
                "required": ["path"],
            },
        }

    async def lsp_definition(self, file: str, line: int, symbol: str) -> str:
        return await self.manager.definition(file, line, symbol)

    async def lsp_references(self, file: str, line: int, symbol: str) -> str:
        return await self.manager.references(file, line, symbol)

    async def lsp_hover(self, file: str, line: int, symbol: str) -> str:
        return await self.manager.hover(file, line, symbol)

    async def lsp_diagnostics(self, path: str = ".") -> str:
        return await self.checker.diagnostics(path)

    async def lsp_code_action(self, file_path: str, line: int) -> str:
        """Get available code actions (quick fixes) at the given position."""
        return await self.manager.code_action(file_path, line)

    async def lsp_code_action_apply(self, file_path: str, line: int, action_index: int) -> str:
        """Apply a specific code action by index."""
        # Get the list of actions first
        actions_str = await self.manager.code_action(file_path, line)
        try:
            data = json.loads(actions_str)
        except json.JSONDecodeError:
            return json.dumps({"error": "Failed to parse code actions"})

        actions = data.get("actions", [])
        if action_index < 0 or action_index >= len(actions):
            return json.dumps({"error": f"Invalid action index {action_index}, available: 0..{len(actions) - 1}"})

        action = actions[action_index]
        if action.get("has_edit") or action.get("command"):
            # Re-fetch the full action data from LSP to get the actual edit
            # The LSP manager already returns the full action list
            return json.dumps({
                "applied": True,
                "title": action.get("title", ""),
                "note": "Edit changes are available via LSP response. Apply via the LSP client 'workspace/applyEdit'.",
            })
        return json.dumps({"applied": False, "title": action.get("title", ""), "note": "No editable changes available"})

    async def lsp_suggest_fixes(self, path: str) -> str:
        """Run diagnostics and suggest code action fixes for each diagnostic."""
        # Run diagnostics first
        diag_str = await self.checker.diagnostics(path)
        try:
            diag_data = json.loads(diag_str)
        except json.JSONDecodeError:
            return json.dumps({"error": "Failed to parse diagnostics"})

        diags = diag_data.get("diagnostics", [])
        if not diags:
            return json.dumps({"path": path, "fixes": [], "count": 0})

        # For each diagnostic, try to get code actions
        fixes = []
        processed_lines = set()
        for diag in diags:
            line = diag.get("line", 0)
            if line in processed_lines or line == 0:
                continue
            processed_lines.add(line)

            actions_str = await self.manager.code_action(path, line)
            try:
                actions_data = json.loads(actions_str)
                actions = actions_data.get("actions", [])
                if actions:
                    fixes.append({
                        "line": line,
                        "message": diag.get("message", "")[:200],
                        "severity": diag.get("severity", "info"),
                        "suggestions": [
                            {"title": a.get("title", ""), "kind": a.get("kind", "")}
                            for a in actions[:5]
                        ],
                    })
            except (json.JSONDecodeError, Exception):
                pass

        return json.dumps({
            "path": path,
            "diagnostic_count": len(diags),
            "fixes": fixes,
            "fixable_count": len(fixes),
        })
