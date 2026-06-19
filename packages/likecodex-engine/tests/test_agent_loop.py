"""Tests for the core agent loop."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_agent_writes_and_runs_hello(tmp_path: Path) -> None:
    tools = ToolRegistry(str(tmp_path))
    context = ContextManager()
    llm = MockProvider.for_hello_world()
    loop = AgentLoop(llm, tools, context)

    outputs = []
    async for resp in loop.run("create hello.py and run it"):
        outputs.append(resp)

    assert len(outputs) >= 3
    hello = tmp_path / "hello.py"
    assert hello.exists()
    assert "hello world" in hello.read_text()

    # The last assistant response should be a text summary.
    assert outputs[-1].content == "Created hello.py and ran it successfully."


@pytest.mark.asyncio
async def test_agent_loop_stops_without_tool_calls() -> None:
    tools = ToolRegistry(str(Path.cwd()))
    context = ContextManager()
    llm = MockProvider(responses=[MockProvider.responses_default()])
    loop = AgentLoop(llm, tools, context)

    outputs = []
    async for resp in loop.run("say hi"):
        outputs.append(resp)

    assert len(outputs) == 1
    assert outputs[0].content == "hi"


def test_tool_registry_lists_builtins() -> None:
    registry = ToolRegistry()
    names = registry.list_tools()
    assert "read_file" in names
    assert "write_file" in names
    assert "run_command" in names
    assert "list_dir" in names
