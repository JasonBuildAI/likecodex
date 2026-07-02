"""Comprehensive tests covering vision tools, background agent,
state machine, dreaming engine, and planner enhancements."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pytest

# ── Vision tools ───────────────────────────────────────────────────────────
from likecodex_engine.tools.vision import (
    vision__image_analyze,
    vision__screenshot_to_code,
)

# ── Background agent ──────────────────────────────────────────────────────
from likecodex_engine.agent.background import (
    BackgroundAgent,
    BackgroundTaskManager,
    BackgroundTaskStatus,
)

# ── State machine ────────────────────────────────────────────────────────
from likecodex_engine.agent.loop_state_machine import (
    AgentState,
    InvalidTransitionError,
    StateMachine,
    build_agent_state_machine,
)

# ── Dreaming engine ──────────────────────────────────────────────────────
from likecodex_engine.agent.dreaming import SessionReviewer

# ── Planner enhanced ─────────────────────────────────────────────────────
from likecodex_engine.agent.planner import Plan, PlanStep, Planner, StepStatus
from likecodex_engine.llm.base import LLMResponse
from likecodex_engine.llm.mock import MockProvider


# ===========================================================================
# Vision Tools
# ===========================================================================


def _create_test_image(tmp_path: Path, name: str = "test.png") -> Path:
    """Create a minimal PNG test image via PIL."""
    from PIL import Image

    img = Image.new("RGBA", (100, 80), (255, 0, 0, 255))
    # Draw a rough "UI" rectangle in the middle
    for x in range(30, 70):
        for y in range(20, 60):
            img.putpixel((x, y), (0, 120, 255, 255))
    path = tmp_path / name
    img.save(path, format="PNG")
    return path


@pytest.mark.asyncio
async def test_vision_image_analyze(tmp_path: Path) -> None:
    """Analyze a test image and verify metadata."""
    img_path = _create_test_image(tmp_path)
    result = await vision__image_analyze(str(img_path))
    data = json.loads(result)

    assert "error" not in data, data.get("error", "")
    assert data["format"] == "PNG"
    assert data["width"] == 100
    assert data["height"] == 80
    assert data["file_name"] == "test.png"


@pytest.mark.asyncio
async def test_vision_image_analyze_with_base64(tmp_path: Path) -> None:
    """Analyze image with base64 encoding enabled."""
    img_path = _create_test_image(tmp_path)
    result = await vision__image_analyze(str(img_path), return_base64=True)
    data = json.loads(result)

    assert "error" not in data
    assert "data_uri" in data
    assert data["data_uri"].startswith("data:image/jpeg;base64,")
    assert data["base64_length"] > 0


@pytest.mark.asyncio
async def test_vision_image_analyze_not_found() -> None:
    """Analyze a non-existent image returns an error."""
    result = await vision__image_analyze("/nonexistent/path/image.png")
    data = json.loads(result)
    assert "error" in data


@pytest.mark.asyncio
async def test_vision_screenshot_to_code(tmp_path: Path) -> None:
    """Analyze a test image as a UI screenshot."""
    img_path = _create_test_image(tmp_path)
    result = await vision__screenshot_to_code(
        str(img_path), context="web app", detail_level="high"
    )
    data = json.loads(result)

    assert "error" not in data, data.get("error", "")
    assert data["image_dimensions"]["width"] == 100
    assert data["image_dimensions"]["height"] == 80
    assert "ui_analysis" in data
    assert "overall_tone" in data["ui_analysis"]
    assert "quadrants" in data["ui_analysis"], "high detail should include quadrants"


@pytest.mark.asyncio
async def test_vision_screenshot_to_code_not_found() -> None:
    """Analyze a non-existent screenshot returns an error."""
    result = await vision__screenshot_to_code("/nonexistent/screenshot.png")
    data = json.loads(result)
    assert "error" in data


# ===========================================================================
# Background Agent
# ===========================================================================


@pytest.mark.asyncio
async def test_background_task_lifecycle() -> None:
    """Test a full background task lifecycle: start, status, cancel."""
    manager = BackgroundTaskManager(max_concurrent=3)

    async def dummy_task(progress_callback=None, **kwargs: Any) -> dict:
        if progress_callback:
            progress_callback(50.0)
        await asyncio.sleep(0.05)
        return {"result": "ok"}

    task_id = await manager.start_task("lifecycle-test", "Test lifecycle", dummy_task)
    assert task_id is not None

    # Small wait for task to start
    await asyncio.sleep(0.05)

    task = manager.get_task(task_id)
    assert task is not None
    assert task.name == "lifecycle-test"

    # Cancel running task
    cancelled = await manager.cancel_task(task_id)
    assert cancelled is True

    # Wait for cancellation to complete
    await asyncio.sleep(0.05)
    status = manager.get_task(task_id)
    assert status is not None
    assert status.status in (
        BackgroundTaskStatus.CANCELLED,
        BackgroundTaskStatus.COMPLETED,
    )


@pytest.mark.asyncio
async def test_background_manager_concurrency() -> None:
    """Test that concurrency limit is respected."""
    manager = BackgroundTaskManager(max_concurrent=2)

    start_time = time.time()
    delay = 0.2

    async def slow_task(progress_callback=None, **kwargs: Any) -> dict:
        await asyncio.sleep(delay)
        return {"done": True}

    # Start 3 tasks (more than max_concurrent=2)
    t1 = await manager.start_task("t1", "Task 1", slow_task)
    t2 = await manager.start_task("t2", "Task 2", slow_task)
    t3 = await manager.start_task("t3", "Task 3", slow_task)

    assert t1 is not None
    assert t2 is not None
    assert t3 is not None

    # Wait for all to complete
    await asyncio.sleep(delay * 2 + 0.1)

    # All should be completed now
    for tid in (t1, t2, t3):
        task = manager.get_task(tid)
        assert task is not None
        assert task.status == BackgroundTaskStatus.COMPLETED, (
            f"Task {tid} status: {task.status}"
        )


@pytest.mark.asyncio
async def test_background_agent_run_tool_task() -> None:
    """Test BackgroundAgent.run_tool_task."""
    async def my_tool(param: str) -> dict:
        await asyncio.sleep(0.02)
        return {"output": f"processed {param}"}

    agent = BackgroundAgent()
    task_id = await agent.run_tool_task("tool-test", "Test tool", my_tool, param="hello")
    assert task_id is not None

    await asyncio.sleep(0.1)
    result = agent.get_results(task_id)
    assert result is not None
    assert result.get("output") == "processed hello"


# ===========================================================================
# State Machine
# ===========================================================================


@pytest.mark.asyncio
async def test_state_machine_transitions() -> None:
    """Test valid transitions of the agent state machine."""
    sm = build_agent_state_machine()

    assert sm.get_current_state() == AgentState.IDLE

    # IDLE -> RUNNING
    await sm.transition("start")
    assert sm.get_current_state() == AgentState.RUNNING

    # RUNNING -> COMPLETED
    await sm.transition("final_answer")
    assert sm.get_current_state() == AgentState.COMPLETED

    # COMPLETED -> IDLE
    await sm.transition("reset")
    assert sm.get_current_state() == AgentState.IDLE


@pytest.mark.asyncio
async def test_state_machine_async_transitions() -> None:
    """Test async transitions with action callbacks."""
    sm = build_agent_state_machine()
    calls: list[str] = []

    sm.add_transition(
        AgentState.RUNNING,
        AgentState.COMPACTING,
        "compact",
        action=lambda ctx: calls.append("compact_action"),
    )

    await sm.transition("start")
    assert sm.get_current_state() == AgentState.RUNNING

    await sm.transition("compact")
    assert sm.get_current_state() == AgentState.COMPACTING
    assert "compact_action" in calls


@pytest.mark.asyncio
async def test_state_machine_can_transition_to() -> None:
    """Test can_transition_to helper."""
    sm = build_agent_state_machine()

    assert sm.can_transition_to(AgentState.RUNNING) is True
    assert sm.can_transition_to(AgentState.ERROR) is False


@pytest.mark.asyncio
async def test_invalid_transition() -> None:
    """Test that invalid transitions raise InvalidTransitionError."""
    sm = build_agent_state_machine()

    with pytest.raises(InvalidTransitionError) as exc_info:
        await sm.transition("final_answer")

    assert exc_info.value.current == AgentState.IDLE
    assert exc_info.value.trigger == "final_answer"


@pytest.mark.asyncio
async def test_state_machine_history() -> None:
    """Test that state machine records transition history."""
    sm = build_agent_state_machine()

    await sm.transition("start")
    await sm.transition("final_answer")

    history = sm.get_history(limit=5)
    assert len(history) == 2

    from_state_1, to_state_1, trigger_1, _ = history[0]
    assert from_state_1 == AgentState.IDLE
    assert to_state_1 == AgentState.RUNNING
    assert trigger_1 == "start"

    from_state_2, to_state_2, trigger_2, _ = history[1]
    assert from_state_2 == AgentState.RUNNING
    assert to_state_2 == AgentState.COMPLETED
    assert trigger_2 == "final_answer"


@pytest.mark.asyncio
async def test_state_machine_reset() -> None:
    """Test resetting the state machine."""
    sm = build_agent_state_machine()
    await sm.transition("start")
    assert sm.get_current_state() == AgentState.RUNNING

    sm.reset()
    assert sm.get_current_state() == AgentState.IDLE
    assert sm.get_history() == []


@pytest.mark.asyncio
async def test_state_machine_listeners() -> None:
    """Test event listeners on state machine."""
    sm = build_agent_state_machine()
    events: list[str] = []

    sm.on("transition", lambda *args: events.append("transition"))
    sm.on("enter_state:running", lambda *args: events.append("enter_running"))

    await sm.transition("start")
    assert "transition" in events
    assert "enter_running" in events


@pytest.mark.asyncio
async def test_state_machine_guard_rejects() -> None:
    """Test that a guard returning False prevents a transition."""
    sm = StateMachine(AgentState.IDLE)

    def reject_guard(ctx: dict | None) -> bool:
        return False

    sm.add_transition(AgentState.IDLE, AgentState.RUNNING, "start", guard=reject_guard)

    # The transition should return False (not raise) when guard rejects
    result = await sm.transition("start")
    assert result is False, "Guard returning False should prevent transition"
    assert sm.get_current_state() == AgentState.IDLE


# ===========================================================================
# Dreaming Engine
# ===========================================================================


@pytest.mark.asyncio
async def test_dreaming_session_review() -> None:
    """Test SessionReviewer with mock session messages."""
    reviewer = SessionReviewer()
    session_id = "test-session-001"

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": "请帮我优化这个函数",
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {"name": "edit_file", "arguments": '{"path": "test.py"}'},
                }
            ],
            "content": "",
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": "File updated successfully.",
        },
        {
            "role": "assistant",
            "content": "注意：重要的是保持代码风格一致。\n- 使用与项目一致的缩进",
        },
    ]

    insight = await reviewer.review_session(session_id, messages)
    assert insight["session_id"] == session_id
    assert len(insight["decisions"]) >= 1
    assert "edit_file" in str(insight["decisions"])
    assert len(insight["learnings"]) >= 1
    assert any("保持代码风格" in l for l in insight["learnings"]) or any("缩进" in l for l in insight["learnings"])
    assert "edit_file" in insight["tools_used"]


@pytest.mark.asyncio
async def test_dreaming_session_review_with_error() -> None:
    """Test SessionReviewer identifies errors in session messages."""
    reviewer = SessionReviewer()
    session_id = "test-session-error"

    messages: list[dict[str, Any]] = [
        {"role": "user", "content": "run the script"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "bash",
                        "arguments": '{"command": "python run.py"}',
                    }
                }
            ],
            "content": "",
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": (
                'Traceback (most recent call last):\n  File "run.py", line 1, in <module>\n'
                "    import missing_module\nImportError: No module named 'missing_module'"
            ),
        },
        {
            "role": "assistant",
            "content": "遇到错误，我来修复它。需要安装 missing_module。",
        },
    ]

    insight = await reviewer.review_session(session_id, messages)
    assert insight["session_id"] == session_id
    assert len(insight["errors_encountered"]) >= 1
    assert any("ImportError" in str(e) for e in insight["errors_encountered"])
    assert "bash" in insight["tools_used"]


# ===========================================================================
# Planner Enhanced
# ===========================================================================


def test_planner_validation_valid_plan() -> None:
    """validate_plan should return True with no issues for a valid plan."""
    plan = Plan(
        task_id="test",
        reasoning="test plan",
        steps=[
            PlanStep(id="1", description="Setup environment", status=StepStatus.COMPLETED),
            PlanStep(id="2", description="Implement feature", depends_on=["1"]),
            PlanStep(id="3", description="Write tests", depends_on=["2"]),
        ],
    )
    valid, issues = Planner.validate_plan(plan)
    assert valid is True, f"Expected valid plan, got issues: {issues}"
    assert issues == []


def test_planner_validation_empty_steps() -> None:
    """validate_plan should reject a plan with no steps."""
    plan = Plan(task_id="test", reasoning="empty")
    valid, issues = Planner.validate_plan(plan)
    assert valid is False
    assert any("no steps" in i.lower() for i in issues)


def test_planner_validation_duplicate_ids() -> None:
    """validate_plan should detect duplicate step IDs."""
    plan = Plan(
        task_id="test",
        reasoning="dup",
        steps=[
            PlanStep(id="1", description="Step A"),
            PlanStep(id="1", description="Step B"),
        ],
    )
    valid, issues = Planner.validate_plan(plan)
    assert valid is False
    assert any("duplicate" in i.lower() for i in issues)


def test_planner_validation_missing_dependency() -> None:
    """validate_plan should detect references to non-existent steps."""
    plan = Plan(
        task_id="test",
        reasoning="missing dep",
        steps=[
            PlanStep(id="1", description="Step A"),
            PlanStep(id="2", description="Step B", depends_on=["3"]),
        ],
    )
    valid, issues = Planner.validate_plan(plan)
    assert valid is False
    assert any("non-existent" in i.lower() for i in issues)


def test_planner_validation_circular_dependency() -> None:
    """validate_plan should detect circular dependencies."""
    plan = Plan(
        task_id="test",
        reasoning="circular",
        steps=[
            PlanStep(id="1", description="Step A", depends_on=["3"]),
            PlanStep(id="2", description="Step B", depends_on=["1"]),
            PlanStep(id="3", description="Step C", depends_on=["2"]),
        ],
    )
    valid, issues = Planner.validate_plan(plan)
    assert valid is False
    assert any("circular" in i.lower() for i in issues)


def test_planner_validation_empty_id_or_description() -> None:
    """validate_plan should detect empty IDs or descriptions."""
    plan = Plan(
        task_id="test",
        reasoning="empty fields",
        steps=[
            PlanStep(id="", description="No ID"),
            PlanStep(id="2", description=""),
        ],
    )
    valid, issues = Planner.validate_plan(plan)
    assert valid is False
    assert any("empty ID" in i for i in issues)
    assert any("empty description" in i for i in issues)


def test_planner_estimate_steps() -> None:
    """estimate_steps should return sensible time estimates."""
    plan = Plan(
        task_id="test",
        reasoning="estimate test",
        steps=[
            PlanStep(id="1", description="Setup project environment"),
            PlanStep(id="2", description="Implement core feature with tests", depends_on=["1"]),
            PlanStep(id="3", description="Deploy to production server", depends_on=["2"]),
        ],
    )
    estimates = Planner.estimate_steps(plan)
    assert "total_seconds" in estimates
    assert "steps" in estimates
    assert len(estimates["steps"]) == 3
    assert estimates["total_seconds"] > 0

    for step_est in estimates["steps"]:
        assert "step_id" in step_est
        assert "estimated_seconds" in step_est
        assert step_est["estimated_seconds"] > 0

    deploy_est = [s for s in estimates["steps"] if "deploy" in s["description"].lower()][0]
    assert deploy_est["estimated_seconds"] >= 90.0


def test_planner_estimate_steps_refactor() -> None:
    """estimate_steps should handle steps with refactor keywords."""
    plan = Plan(
        task_id="test",
        reasoning="refactor test",
        steps=[
            PlanStep(id="1", description="Refactor the entire authentication module"),
        ],
    )
    estimates = Planner.estimate_steps(plan)
    assert estimates["steps"][0]["estimated_seconds"] >= 120.0


@pytest.mark.asyncio
async def test_planner_incremental_replan() -> None:
    """Test incremental_replan preserves completed steps and replans remaining."""
    mock_llm = MockProvider(
        responses=[
            LLMResponse(
                content=json.dumps({
                    "reasoning": "simplified approach after failure",
                    "steps": [
                        {
                            "id": "2",
                            "description": "Re-implement feature (fixed)",
                            "depends_on": ["1"],
                        },
                        {"id": "3", "description": "Verify tests pass", "depends_on": ["2"]},
                    ],
                }),
            ),
        ],
    )
    planner = Planner(mock_llm)

    original_plan = Plan(
        task_id="replan-test",
        reasoning="original plan",
        steps=[
            PlanStep(id="1", description="Setup environment", status=StepStatus.COMPLETED),
            PlanStep(id="2", description="Implement feature"),
            PlanStep(id="3", description="Write tests"),
            PlanStep(id="4", description="Deploy"),
        ],
    )

    new_plan = await planner.incremental_replan(
        current_plan=original_plan,
        completed_steps=["1"],
        failed_step="2",
        error_info="ImportError: missing dependency",
    )

    # Completed step should be preserved
    assert len(new_plan.steps) > 0
    assert new_plan.steps[0].id == "1"
    assert new_plan.steps[0].description == "Setup environment"

    # The plan reasoning should mention the failure
    assert (
        "failed" in new_plan.reasoning.lower()
        or "replan" in new_plan.reasoning.lower()
        or "incremental" in new_plan.reasoning.lower()
    )


@pytest.mark.asyncio
async def test_planner_incremental_replan_fallback() -> None:
    """When LLM returns invalid JSON, replan should fallback to keeping remaining steps."""
    mock_llm = MockProvider(
        responses=[
            LLMResponse(content="invalid json {{"),
        ],
    )
    planner = Planner(mock_llm)

    original_plan = Plan(
        task_id="replan-fallback",
        reasoning="original",
        steps=[
            PlanStep(id="1", description="Setup", status=StepStatus.COMPLETED),
            PlanStep(id="2", description="Implement"),
            PlanStep(id="3", description="Test"),
        ],
    )

    new_plan = await planner.incremental_replan(
        current_plan=original_plan,
        completed_steps=["1"],
        failed_step="2",
        error_info="timeout",
    )

    # Should still have all steps (completed preserved + remaining as fallback)
    assert len(new_plan.steps) == 3
    assert new_plan.steps[0].id == "1"
