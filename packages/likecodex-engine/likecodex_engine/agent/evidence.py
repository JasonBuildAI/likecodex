"""Per-turn evidence ledger for host-verified tool receipts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

WRITE_TOOLS = frozenset(
    {
        "write_file",
        "edit_file",
        "multi_edit",
        "move_file",
        "notebook_edit",
        "delete_range",
        "delete_symbol",
    }
)


def command_matches(expected: str, actual: str) -> bool:
    expected = expected.strip()
    actual = actual.strip()
    if not expected or not actual:
        return False
    if expected == actual:
        return True
    return actual.startswith(expected) or expected.startswith(actual)


@dataclass
class Receipt:
    tool_name: str
    success: bool
    command: str = ""
    step: str = ""
    paths: list[str] = field(default_factory=list)
    todos: list[dict[str, Any]] = field(default_factory=list)
    read_only: bool = False


class EvidenceLedger:
    """In-memory receipts for the current user turn."""

    def __init__(self) -> None:
        self._receipts: list[Receipt] = []

    def reset(self) -> None:
        self._receipts.clear()

    def record(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        success: bool,
        read_only: bool = False,
        step: str = "",
    ) -> None:
        command = ""
        paths: list[str] = []
        todos: list[dict[str, Any]] = []
        if tool_name == "run_command":
            command = str(arguments.get("command", "")).strip()
        elif tool_name in WRITE_TOOLS or tool_name == "git_commit":
            for key in ("path", "file_path"):
                if key in arguments:
                    paths.append(str(arguments[key]))
        elif tool_name == "complete_step":
            step = str(arguments.get("step", step)).strip()
        elif tool_name == "todo_write":
            todos = list(arguments.get("todos") or [])

        self._receipts.append(
            Receipt(
                tool_name=tool_name,
                success=success,
                command=command,
                step=step,
                paths=paths,
                todos=todos,
                read_only=read_only,
            )
        )

    def has_successful_command(self, command: str) -> bool:
        command = command.strip()
        return any(
            r.success and r.tool_name == "run_command" and command_matches(command, r.command) for r in self._receipts
        )

    def has_successful_command_after(self, command: str, after_index: int) -> bool:
        command = command.strip()
        for r in self._receipts[after_index + 1 :]:
            if r.success and r.tool_name == "run_command" and command_matches(command, r.command):
                return True
        return False

    def latest_successful_writer_index(self) -> tuple[int, bool]:
        for idx in range(len(self._receipts) - 1, -1, -1):
            r = self._receipts[idx]
            if r.success and r.tool_name in WRITE_TOOLS | {"git_commit"}:
                return idx, True
        return -1, False

    def has_successful_complete_step(self, step: str) -> bool:
        step = step.strip().lower()
        if not step:
            return False
        for r in self._receipts:
            if not r.success or r.tool_name != "complete_step":
                continue
            if step in r.step.lower() or r.step.lower() in step:
                return True
        return False

    def incomplete_todos(self) -> list[dict[str, Any]]:
        todos = self.latest_todos()
        if not todos:
            return []
        return [t for t in todos if str(t.get("status", "")).lower() not in {"completed", "cancelled"}]

    def latest_todos(self) -> list[dict[str, Any]]:
        for r in reversed(self._receipts):
            if r.success and r.tool_name == "todo_write" and r.todos:
                return list(r.todos)
        return []

    def has_successful_todo_write(self) -> bool:
        return any(r.success and r.tool_name == "todo_write" for r in self._receipts)

    def newly_completed_without_receipt(
        self,
        previous: list[dict[str, Any]],
        updated: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        prev_status = {str(t.get("id", i)): str(t.get("status", "")) for i, t in enumerate(previous)}
        missing: list[dict[str, Any]] = []
        for item in updated:
            item_id = str(item.get("id", ""))
            new_status = str(item.get("status", ""))
            old_status = prev_status.get(item_id, "pending")
            if new_status == "completed" and old_status != "completed":
                label = str(item.get("content", item_id))
                if not self.has_successful_complete_step(label) and not self.has_successful_complete_step(item_id):
                    missing.append(item)
        return missing
