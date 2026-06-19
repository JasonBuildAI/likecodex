"""complete_step verification tests."""

import json

import pytest
from likecodex_engine.llm.base import Message, Role
from likecodex_engine.tools.plan_progress import PlanProgressTools
from likecodex_engine.tools.todo import TodoTools


def _session_with_command(cmd: str) -> list[Message]:
    return [
        Message(
            role=Role.TOOL,
            content=json.dumps({"command": cmd, "exit_code": 0, "stdout": "ok"}),
            tool_call_id="1",
        )
    ]


@pytest.mark.asyncio
async def test_verification_rejects_unknown_command():
    tools = PlanProgressTools(session_log_provider=lambda: [])
    out = json.loads(
        await tools.complete_step(
            "step1",
            "tests pass",
            [{"kind": "verification", "summary": "ran tests", "command": "go test ./..."}],
        )
    )
    assert out["accepted"] is False


@pytest.mark.asyncio
async def test_verification_accepts_session_command():
    cmd = "pytest -q"
    tools = PlanProgressTools(session_log_provider=lambda: _session_with_command(cmd))
    out = json.loads(
        await tools.complete_step(
            "step1",
            "tests pass",
            [{"kind": "verification", "summary": "ran tests", "command": cmd}],
        )
    )
    assert out["accepted"] is True


@pytest.mark.asyncio
async def test_complete_step_advances_todo():
    todo = TodoTools()
    await todo.todo_write(
        [
            {"id": "1", "content": "fix bug", "status": "in_progress"},
            {"id": "2", "content": "add test", "status": "pending"},
        ]
    )
    tools = PlanProgressTools(lambda: [], todo)
    await tools.complete_step("fix bug", "done", [{"kind": "manual", "summary": "verified manually"}])
    current = todo.current()
    assert current[0]["status"] == "completed"
    assert current[1]["status"] == "in_progress"
