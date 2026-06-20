"""Subagent transcript store tests."""

import json

import pytest
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.agent.subagent_store import SubagentSpec, SubagentStore
from likecodex_engine.agent.task import TaskTool
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


def test_prepare_continue_loads_messages(tmp_path):
    store = SubagentStore(str(tmp_path))
    spec = SubagentSpec(name="review", parent_session="sess-1", workspace_root=str(tmp_path))
    run = store.prepare_fresh(spec)
    store.save_completed(run, [])
    continued = store.prepare_continue(run.ref, spec)
    assert continued.ref == run.ref


def test_fork_creates_new_ref(tmp_path):
    store = SubagentStore(str(tmp_path))
    spec = SubagentSpec(name="review", parent_session="sess-1", workspace_root=str(tmp_path))
    run = store.prepare_fresh(spec)
    store.save_completed(run, [])
    forked = store.prepare_fork(run.ref, spec)
    assert forked.ref != run.ref


def test_continue_rejects_other_parent_session(tmp_path):
    store = SubagentStore(str(tmp_path))
    spec = SubagentSpec(name="review", parent_session="sess-1", workspace_root=str(tmp_path))
    run = store.prepare_fresh(spec)
    store.save_completed(run, [])
    other = SubagentSpec(name="review", parent_session="sess-2", workspace_root=str(tmp_path))
    with pytest.raises(ValueError, match="fork_from"):
        store.prepare_continue(run.ref, other)


def test_cleanup_stale_running_marks_interrupted(tmp_path):
    store = SubagentStore(str(tmp_path))
    spec = SubagentSpec(name="review", parent_session="sess-1", workspace_root=str(tmp_path))
    run = store.prepare_fresh(spec)
    run.release()
    assert run.meta.status == "running"
    cleaned = store.cleanup_stale_running()
    assert cleaned == 1
    meta = json.loads((tmp_path / ".likecodex" / "subagents" / f"{run.ref}.meta.json").read_text())
    assert meta["status"] == "interrupted"
    with pytest.raises(ValueError, match="interrupted"):
        store.prepare_continue(run.ref, spec)


@pytest.mark.asyncio
async def test_task_persists_subagent_ref(tmp_path):
    parent = ToolRegistry(str(tmp_path), register_defaults=False)
    parent.register(
        "read_file", {"description": "x", "parameters": {"type": "object", "properties": {}}}, lambda **_: "{}"
    )

    def factory(wl, ms):
        sub = ToolRegistry(str(tmp_path), register_defaults=False)
        return AgentLoop(
            MockProvider(responses=[LLMResponse(content="done")]),
            sub,
            ContextManager(system_prompt="sub"),
            permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
            is_subagent=True,
        )

    store = SubagentStore(str(tmp_path))
    tool = TaskTool(factory, store=store, parent_session="sess-a", working_dir=str(tmp_path))
    out = json.loads(await tool.task("inspect code", description="review"))
    assert out["subagent_ref"].startswith("sa_")

    continued = json.loads(await tool.task("continue review", description="review", continue_from=out["subagent_ref"]))
    assert "result" in continued
