#!/usr/bin/env python3
"""Agent task benchmark (mock LLM) for parity regression."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path

from likecodex_engine.agent.coordinator import format_handoff
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.cache_first import CacheFirstContext
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse, ToolCall
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry

DEFAULT_BASELINE = Path(__file__).resolve().parent / "baseline.json"
REGRESSION_RATIO = 0.20


async def run_scenario(
    name: str,
    responses: list[LLMResponse],
    *,
    handoff: bool = False,
    context: ContextManager | None = None,
) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        tools = ToolRegistry(tmp)
        loop = AgentLoop(
            MockProvider(responses=responses),
            tools,
            context or ContextManager(system_prompt="benchmark"),
            permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
            executor_handoff_guard=handoff,
        )
        prompt = (
            format_handoff(f"benchmark task: {name}", "Plan: inspect workspace and act")
            if handoff
            else f"benchmark task: {name}"
        )
        steps = 0
        tool_failures = 0
        compactions = 0
        async for resp in loop.run(prompt):
            steps += 1
            if resp.event_type in ("compaction_started", "compaction_done", "compaction"):
                compactions += 1
            if resp.event_type == "tool_result" and '"error"' in (resp.content or "")[:200]:
                tool_failures += 1
        return {
            "scenario": name,
            "steps": steps,
            "tool_failures": tool_failures,
            "compactions": compactions,
        }


async def run_compaction_scenario() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        ctx = CacheFirstContext(system_prompt="benchmark")
        ctx.set_working_dir(tmp)
        ctx.set_compact_llm(MockProvider(responses=[LLMResponse(content="summary")]))
        for i in range(4):
            ctx.add_user_message(f"user {i}")
            ctx.add_assistant_message(content=f"assistant {i}")
        ctx.last_prompt_tokens = int(ctx.compactor.context_window * 0.9)
        return await run_scenario(
            "context_compact",
            [LLMResponse(content="done after compact")],
            context=ctx,
        )


def check_regression(current: list[dict], baseline: list[dict]) -> list[str]:
    errors: list[str] = []
    baseline_map = {item["scenario"]: item for item in baseline}
    for item in current:
        base = baseline_map.get(item["scenario"])
        if not base:
            errors.append(f"missing baseline scenario: {item['scenario']}")
            continue
        limit = int(base["steps"] * (1 + REGRESSION_RATIO)) + 1
        if item["steps"] > limit:
            errors.append(
                f"{item['scenario']}: steps {item['steps']} exceeded baseline {base['steps']} (+{REGRESSION_RATIO:.0%})"
            )
        if item["tool_failures"] > base["tool_failures"]:
            errors.append(
                f"{item['scenario']}: tool_failures {item['tool_failures']} > baseline {base['tool_failures']}"
            )
        if item["scenario"] == "context_compact" and item["compactions"] < base.get("compactions", 2):
            errors.append(
                f"{item['scenario']}: compactions {item['compactions']} below baseline {base.get('compactions', 2)}"
            )
    return errors


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_BASELINE))
    parser.add_argument("--check", action="store_true", help="Fail when results regress vs baseline")
    args = parser.parse_args()

    scenarios = [
        (
            "fix_bug",
            [
                LLMResponse(
                    content="",
                    tool_calls=[
                        ToolCall(id="1", name="read_file", arguments={"path": "main.py", "offset": 1, "limit": 20})
                    ],
                ),
                LLMResponse(content="Fixed the bug."),
            ],
        ),
        (
            "plan_readonly",
            [
                LLMResponse(
                    content="",
                    tool_calls=[
                        ToolCall(id="1", name="grep_files", arguments={"pattern": "TODO", "max_results": 5})
                    ],
                ),
                LLMResponse(content="Found todos."),
            ],
        ),
        (
            "handoff_guard",
            [
                LLMResponse(content="Only describing the plan."),
                LLMResponse(
                    content="",
                    tool_calls=[ToolCall(id="1", name="read_file", arguments={"path": "main.py"})],
                ),
                LLMResponse(content="Proceeding after read."),
            ],
        ),
    ]

    results = []
    for name, responses in scenarios:
        results.append(await run_scenario(name, responses, handoff=name == "handoff_guard"))
    results.append(await run_compaction_scenario())

    payload = {"results": results}
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    if args.check:
        if not out.exists():
            print(f"baseline missing at {out}; run without --check first", file=sys.stderr)
            raise SystemExit(1)
        baseline = json.loads(out.read_text(encoding="utf-8")).get("results", [])
        errors = check_regression(results, baseline)
        if errors:
            for err in errors:
                print(err, file=sys.stderr)
            raise SystemExit(1)
        print(json.dumps({"ok": True, "results": results}, indent=2))
        return

    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
