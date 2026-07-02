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
from likecodex_engine.agent.goal import GoalState
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.agent.plan_state import PlanState
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


async def run_goal_scenario() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        tools = ToolRegistry(tmp)
        goal = GoalState(max_continuations=5)
        goal.start("ship feature")
        loop = AgentLoop(
            MockProvider(
                responses=[
                    LLMResponse(content="Step one done. [goal:continue]"),
                    LLMResponse(content="All done. [goal:complete]"),
                ]
            ),
            tools,
            ContextManager(system_prompt="benchmark"),
            permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
            goal_state=goal,
        )
        steps = 0
        async for _ in loop.run("benchmark goal"):
            steps += 1
        return {"scenario": "goal_continuation", "steps": steps, "tool_failures": 0, "compactions": 0}


async def run_plan_window_scenario() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        tools = ToolRegistry(tmp)
        plan = PlanState()
        plan.approve_exit()
        loop = AgentLoop(
            MockProvider(
                responses=[
                    LLMResponse(
                        content="",
                        tool_calls=[
                            ToolCall(id="1", name="write_file", arguments={"path": "a.txt", "content": "x"})
                        ],
                    ),
                    LLMResponse(content="Written during execution window."),
                ]
            ),
            tools,
            ContextManager(system_prompt="benchmark"),
            permission_evaluator=PermissionEvaluator(ApprovalMode.ASK),
            plan_state=plan,
        )
        steps = 0
        tool_failures = 0
        async for resp in loop.run("execute approved plan"):
            steps += 1
            if resp.event_type == "tool_result" and '"error"' in (resp.content or "")[:200]:
                tool_failures += 1
        return {
            "scenario": "plan_execution_window",
            "steps": steps,
            "tool_failures": tool_failures,
            "compactions": 0,
        }


# ---------------------------------------------------------------------------
# SWE-bench inspired scenario definitions
# ---------------------------------------------------------------------------
SWE_BENCH_TASKS: list[tuple[str, list[LLMResponse]]] = [
    (
        "swe_parse_error",
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="1", name="read_file", arguments={"path": "parser.py", "offset": 1, "limit": 50}),
                ],
            ),
            LLMResponse(content="Found the parse error at line 42."),
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="2",
                        name="edit_file",
                        arguments={"path": "parser.py", "old_string": "except:", "new_string": "except ValueError as e:"},
                    ),
                ],
            ),
            LLMResponse(content="Fixed the bare except clause."),
        ],
    ),
    (
        "swe_import_order",
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="1", name="grep_files", arguments={"pattern": "^import", "include": "*.py", "max_results": 10}),
                ],
            ),
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="2", name="read_file", arguments={"path": "main.py", "offset": 1, "limit": 30}),
                ],
            ),
            LLMResponse(content="Reordered imports per PEP8."),
        ],
    ),
    (
        "swe_type_error",
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="1", name="read_file", arguments={"path": "utils.py", "offset": 1, "limit": 100}),
                ],
            ),
            LLMResponse(content="Found Optional[str] vs str mismatch."),
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="2",
                        name="edit_file",
                        arguments={"path": "utils.py", "old_string": "def get_name() -> str:", "new_string": "def get_name() -> Optional[str]:"},
                    ),
                ],
            ),
            LLMResponse(content="Fixed the type annotation."),
        ],
    ),
    (
        "swe_missing_import",
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="1", name="grep_files", arguments={"pattern": "Path\\(", "include": "*.py", "max_results": 5}),
                ],
            ),
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="2",
                        name="edit_file",
                        arguments={"path": "utils.py", "old_string": "from pathlib", "new_string": "from pathlib import Path"},
                    ),
                ],
            ),
            LLMResponse(content="Added missing import."),
        ],
    ),
    (
        "swe_logic_negation",
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="1", name="read_file", arguments={"path": "validator.py", "offset": 1, "limit": 80}),
                ],
            ),
            LLMResponse(content="Found inverted condition at line 55."),
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="2",
                        name="edit_file",
                        arguments={"path": "validator.py", "old_string": "if not enabled and user.is_admin():", "new_string": "if enabled and user.is_admin():"},
                    ),
                ],
            ),
            LLMResponse(content="Fixed the logic negation bug."),
        ],
    ),
]


async def run_swe_scenario(name: str, responses: list[LLMResponse]) -> dict:
    """Run a SWE-bench inspired scenario with the full agent loop."""
    return await run_scenario(name, responses)


async def main() -> None:
    parser = argparse.ArgumentParser(description="LikeCodex agent performance benchmark (SWE-bench subset)")
    parser.add_argument("--output", default=str(DEFAULT_BASELINE))
    parser.add_argument("--check", action="store_true", help="Fail when results regress vs baseline")
    parser.add_argument("--swe-bench", action="store_true", help="Include SWE-bench inspired scenarios")
    parser.add_argument("--report", type=str, help="Path to write JSON benchmark report")
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

    if args.swe_bench:
        for name, responses in SWE_BENCH_TASKS:
            results.append(await run_swe_scenario(name, responses))

    results.append(await run_compaction_scenario())
    results.append(await run_goal_scenario())
    results.append(await run_plan_window_scenario())

    payload = {
        "benchmark_version": "1.0",
        "total_scenarios": len(results),
        "results": results,
    }

    # Write JSON report if requested
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "metadata": {
                "benchmark": "LikeCodex Agent Performance",
                "version": "8.6",
                "args": vars(args),
            },
            "scenarios": results,
        }
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Report written to {report_path}")

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
