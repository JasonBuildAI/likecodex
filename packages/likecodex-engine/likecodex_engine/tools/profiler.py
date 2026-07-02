"""Performance profiling and benchmarking tools."""

from __future__ import annotations

import io
import json
import pstats
import time
import timeit
from typing import Any


class ProfilerTools:
    """Tools for profiling Python code performance and memory usage."""

    @staticmethod
    def profile_python_schema() -> dict[str, Any]:
        return {
            "description": "Run cProfile on a Python script and return a sorted stats summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "Python code to profile (as a string)",
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": ["cumtime", "tottime", "ncalls"],
                        "default": "cumtime",
                        "description": "Sort field for profile output",
                    },
                    "top_n": {
                        "type": "integer",
                        "default": 20,
                        "description": "Number of top functions to show",
                    },
                },
                "required": ["script"],
            },
        }

    @staticmethod
    def profile_function_schema() -> dict[str, Any]:
        return {
            "description": "Benchmark a Python code snippet using timeit with configurable iterations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code snippet to benchmark",
                    },
                    "iterations": {
                        "type": "integer",
                        "default": 1000,
                        "description": "Number of iterations",
                    },
                    "repeat": {
                        "type": "integer",
                        "default": 5,
                        "description": "Number of repeat runs",
                    },
                },
                "required": ["code"],
            },
        }

    @staticmethod
    def memory_profile_schema() -> dict[str, Any]:
        return {
            "description": "Profile memory usage of a Python code snippet (requires memory_profiler).",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to profile memory usage",
                    },
                },
                "required": ["code"],
            },
        }

    async def profile_python(
        self,
        script: str,
        sort_by: str = "cumtime",
        top_n: int = 20,
    ) -> str:
        try:
            import cProfile  # noqa: F811
        except ImportError:
            return json.dumps({"error": "cProfile not available"})

        try:
            profiler = cProfile.Profile()
            profiler.enable()
            compiled = compile(script, "<profile>", "exec")
            exec(compiled, {})  # noqa: S102
            profiler.disable()

            buf = io.StringIO()
            ps = pstats.Stats(profiler, stream=buf)
            ps.sort_stats(sort_by)
            ps.print_stats(top_n)
            output = buf.getvalue()

            return json.dumps({
                "sort_by": sort_by,
                "top_n": top_n,
                "output": output,
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def profile_function(
        self,
        code: str,
        iterations: int = 1000,
        repeat: int = 5,
    ) -> str:
        try:
            stmt = code.strip()
            times = timeit.repeat(stmt, repeat=repeat, number=iterations)
            return json.dumps({
                "code": stmt,
                "iterations": iterations,
                "repeat": repeat,
                "min": round(min(times), 6),
                "max": round(max(times), 6),
                "avg": round(sum(times) / len(times), 6),
                "total": round(sum(times), 6),
                "per_iteration": round(sum(times) / (iterations * repeat), 9),
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def memory_profile(self, code: str) -> str:
        try:
            from memory_profiler import memory_usage  # type: ignore[import-untyped]
        except ImportError:
            return json.dumps({
                "error": "memory_profiler not installed. Install with: pip install memory_profiler",
            })

        try:
            compiled = compile(code.strip(), "<memory_profile>", "exec")

            def target() -> None:
                exec(compiled, {})  # noqa: S102

            mem_usage = memory_usage(target, interval=0.1, timeout=None)
            return json.dumps({
                "code": code,
                "mem_min_mib": round(min(mem_usage), 2) if mem_usage else 0,
                "mem_max_mib": round(max(mem_usage), 2) if mem_usage else 0,
                "mem_avg_mib": round(sum(mem_usage) / len(mem_usage), 2) if mem_usage else 0,
                "samples": len(mem_usage),
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
