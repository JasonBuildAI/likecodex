"""Edit cells of a Jupyter notebook (.ipynb) safely within the workspace."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from likecodex_engine.tools.path_utils import resolve_in_working_dir

_VALID_CELL_TYPES = {"code", "markdown", "raw"}


class NotebookTools:
    def __init__(self, working_dir: str) -> None:
        self.working_dir = Path(working_dir).resolve()

    def notebook_edit_schema(self) -> dict[str, Any]:
        return {
            "description": (
                "Edit a Jupyter notebook cell. mode=replace overwrites a cell, "
                "insert adds a new cell at index, delete removes a cell."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative .ipynb path"},
                    "cell_index": {"type": "integer", "description": "0-based cell index"},
                    "mode": {
                        "type": "string",
                        "enum": ["replace", "insert", "delete"],
                        "default": "replace",
                    },
                    "source": {"type": "string", "description": "New cell source (replace/insert)"},
                    "cell_type": {
                        "type": "string",
                        "enum": sorted(_VALID_CELL_TYPES),
                        "default": "code",
                    },
                },
                "required": ["path", "cell_index"],
            },
        }

    async def notebook_edit(
        self,
        path: str,
        cell_index: int,
        mode: str = "replace",
        source: str = "",
        cell_type: str = "code",
    ) -> str:
        try:
            target = resolve_in_working_dir(self.working_dir, path)
        except PermissionError as exc:
            return json.dumps({"error": str(exc)})
        if not target.exists():
            return json.dumps({"error": f"Notebook not found: {path}"})
        if cell_type not in _VALID_CELL_TYPES:
            return json.dumps({"error": f"Invalid cell_type: {cell_type}"})

        try:
            nb = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return json.dumps({"error": f"Cannot parse notebook: {exc}"})

        cells = nb.setdefault("cells", [])
        source_lines = self._to_source_lines(source)

        if mode == "insert":
            if cell_index < 0 or cell_index > len(cells):
                return json.dumps({"error": f"insert index out of range: {cell_index}"})
            cells.insert(cell_index, self._new_cell(cell_type, source_lines))
        elif mode == "delete":
            if cell_index < 0 or cell_index >= len(cells):
                return json.dumps({"error": f"delete index out of range: {cell_index}"})
            cells.pop(cell_index)
        else:  # replace
            if cell_index < 0 or cell_index >= len(cells):
                return json.dumps({"error": f"replace index out of range: {cell_index}"})
            cell = cells[cell_index]
            cell["source"] = source_lines
            cell["cell_type"] = cell_type
            if cell_type == "code":
                cell.setdefault("outputs", [])
                cell.setdefault("execution_count", None)
            else:
                cell.pop("outputs", None)
                cell.pop("execution_count", None)

        target.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
        return json.dumps({"path": path, "mode": mode, "cell_index": cell_index, "cells": len(cells)})

    @staticmethod
    def _to_source_lines(source: str) -> list[str]:
        if not source:
            return []
        parts = source.splitlines(keepends=True)
        return parts

    @staticmethod
    def _new_cell(cell_type: str, source_lines: list[str]) -> dict[str, Any]:
        cell: dict[str, Any] = {"cell_type": cell_type, "metadata": {}, "source": source_lines}
        if cell_type == "code":
            cell["outputs"] = []
            cell["execution_count"] = None
        return cell
