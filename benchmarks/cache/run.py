#!/usr/bin/env python3
"""Measure LikeCodex prefix-cache hit rate over multi-turn sessions."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "likecodex-engine"))

from likecodex_engine.agent.loop import AgentLoop  # noqa: E402
from likecodex_engine.context.cache_first import CacheFirstContext  # noqa: E402
from likecodex_engine.llm.cache_metrics import CacheMetrics, reset_global_cache_metrics  # noqa: E402
from likecodex_engine.llm.mock import MockProvider  # noqa: E402
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator  # noqa: E402
from likecodex_engine.tools.registry import ToolRegistry  # noqa: E402

# DeepSeek V4-Flash pricing (USD per 1M tokens, 2026-04)
PRICE_CACHE_HIT = 0.0028
PRICE_CACHE_MISS = 0.14


async def run_benchmark(turns: int, simulate_cache: bool) -> dict:
    reset_global_cache_metrics()
    metrics = CacheMetrics()
    tools = ToolRegistry(str(ROOT))
    context = CacheFirstContext()
    llm = MockProvider.for_cache_test() if simulate_cache else MockProvider(
        responses=[MockProvider.responses_default()] * turns
    )
    loop = AgentLoop(
        llm,
        tools,
        context,
        permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
    )

    turn_stats: list[dict] = []
    prefix_hash = context.prefix_hash()

    for turn in range(1, turns + 1):
        prompt = f"Turn {turn}: list project files and summarize."
        turn_hits_before = metrics.total_hit_tokens
        turn_miss_before = metrics.total_miss_tokens

        async for resp in loop.run(prompt):
            metrics.record(resp.usage)

        turn_hit = metrics.total_hit_tokens - turn_hits_before
        turn_miss = metrics.total_miss_tokens - turn_miss_before
        turn_total = turn_hit + turn_miss
        turn_stats.append(
            {
                "turn": turn,
                "hit_tokens": turn_hit,
                "miss_tokens": turn_miss,
                "hit_rate": round(turn_hit / turn_total, 4) if turn_total else 0.0,
                "prefix_hash": context.prefix_hash(),
            }
        )

    total = metrics.total_hit_tokens + metrics.total_miss_tokens
    hit_rate = metrics.hit_rate
    cost = (metrics.total_hit_tokens * PRICE_CACHE_HIT + metrics.total_miss_tokens * PRICE_CACHE_MISS) / 1_000_000
    no_cache_cost = total * PRICE_CACHE_MISS / 1_000_000

    return {
        "turns": turns,
        "simulate_cache": simulate_cache,
        "prefix_hash": prefix_hash,
        "prefix_hash_stable": all(t["prefix_hash"] == prefix_hash for t in turn_stats),
        "overall_hit_rate": round(hit_rate, 4),
        "turn_stats": turn_stats,
        "total_hit_tokens": metrics.total_hit_tokens,
        "total_miss_tokens": metrics.total_miss_tokens,
        "estimated_cost_usd": round(cost, 6),
        "estimated_cost_without_cache_usd": round(no_cache_cost, 6),
        "savings_pct": round((1 - cost / no_cache_cost) * 100, 2) if no_cache_cost else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="LikeCodex cache benchmark")
    parser.add_argument("--turns", type=int, default=10)
    parser.add_argument("--simulate-cache", action="store_true", default=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "baseline.json")
    args = parser.parse_args()

    result = asyncio.run(run_benchmark(args.turns, args.simulate_cache))
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(result, indent=2))
    print(f"\nWrote {args.output}")

    if result["turns"] >= 5:
        turn5 = next((t for t in result["turn_stats"] if t["turn"] == 5), None)
        if turn5 and turn5["hit_rate"] < 0.85 and args.simulate_cache:
            print("WARNING: turn 5 hit_rate below 85% target", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
