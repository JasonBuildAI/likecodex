"""Test discovery and execution tools for the agent."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from likecodex_engine.debug.test_runner import TestRunnerService


class TestRunner:
    """Discovers and runs tests, returning JSON results for the agent."""

    def __init__(self, working_dir: str) -> None:
        self.working_dir = Path(working_dir).resolve()
        self._service = TestRunnerService(str(self.working_dir))

    def discover_tests_schema(self) -> dict[str, Any]:
        return {
            "description": "Discover all test files and test cases in the workspace (pytest, vitest/jest, cargo-test).",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Optional substring filter on test name",
                    },
                },
            },
        }

    async def discover_tests(self, filter: str = "") -> str:
        """Discover tests, optionally filtered by name."""
        try:
            raw = await self._service.discover_tests()
            test_files = raw.get("testFiles", [])

            if filter:
                filtered = []
                for tf in test_files:
                    matching = [t for t in tf.get("tests", []) if filter.lower() in t.get("name", "").lower()]
                    if matching:
                        filtered.append({**tf, "tests": matching})
                test_files = filtered

            total = sum(len(tf.get("tests", [])) for tf in test_files)
            return json.dumps({
                "test_files": test_files,
                "total_test_cases": total,
                "file_count": len(test_files),
            })
        except Exception as e:
            return json.dumps({"error": f"Test discovery failed: {e}"})

    def run_tests_schema(self) -> dict[str, Any]:
        return {
            "description": "Run discovered tests and return results. Optionally filter by test name substring.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Optional substring filter on test name",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout per test in seconds",
                        "default": 120,
                    },
                },
            },
        }

    async def run_tests(self, filter: str = "", timeout: int = 120) -> str:
        """Run tests and collect all results."""
        try:
            results = []
            passed = 0
            failed = 0
            error_details = []

            # Collect events from the async generator
            async for event in self._service.run_tests(test_filter=filter):
                if event.get("type") == "test_result":
                    results.append({
                        "testId": event.get("testId"),
                        "name": event.get("name", ""),
                        "status": event.get("status"),
                        "duration": event.get("duration", 0),
                        "error": event.get("error", ""),
                    })
                    if event.get("status") == "passed":
                        passed += 1
                    elif event.get("status") == "failed":
                        failed += 1
                        error_details.append({
                            "test": event.get("name"),
                            "error": event.get("error", ""),
                        })
                elif event.get("type") == "done":
                    total = event.get("total", 0)

            return json.dumps({
                "results": results,
                "passed": passed,
                "failed": failed,
                "total": len(results),
                "errors": error_details if error_details else None,
            })
        except Exception as e:
            return json.dumps({"error": f"Test run failed: {e}"})
