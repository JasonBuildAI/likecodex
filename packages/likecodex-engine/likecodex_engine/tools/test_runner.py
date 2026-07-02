"""Test discovery and execution tools for the agent."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import aiohttp

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

    def analyze_failures_schema(self) -> dict[str, Any]:
        return {
            "description": "Analyze failed test output using LLM to identify root causes and suggest fixes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "errors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of error messages or stack traces from failed tests",
                    },
                },
                "required": ["errors"],
            },
        }

    async def analyze_failures(self, errors: list[str]) -> str:
        """Use LLM to analyze test failure output and suggest root causes."""
        if not errors:
            return json.dumps({"analysis": [], "message": "No errors to analyze."})

        # Try calling an LLM through the engine's configured API
        llm_api = os.environ.get("LIKECODEX_LLM_API_URL", "")
        api_key = os.environ.get("LIKECODEX_LLM_API_KEY", "")

        if llm_api and api_key:
            prompt = (
                "Analyze the following test failures. For each failure, identify:\n"
                "1. Root cause (what went wrong)\n"
                "2. Likely location (file, function, assertion)\n"
                "3. Suggested fix\n\n"
                "Failures:\n"
            )
            for i, err in enumerate(errors, 1):
                prompt += f"\n--- Failure {i} ---\n{err[:2000]}\n"

            try:
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "model": os.environ.get("LIKECODEX_LLM_MODEL", "deepseek-chat"),
                        "messages": [
                            {"role": "system", "content": "You are a test failure analysis expert. Be concise and specific."},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 2048,
                    }
                    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                    async with session.post(llm_api, json=payload, headers=headers, timeout=30) as resp:
                        if resp.ok:
                            data = await resp.json()
                            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                            return json.dumps({
                                "method": "llm",
                                "analysis": content,
                                "failures_analyzed": len(errors),
                            })
            except Exception:
                pass

        # Fallback: rule-based analysis
        analysis = []
        for err in errors:
            err_lower = err.lower()
            cause = "unknown"
            suggestion = ""
            if "assertionerror" in err_lower or "assert " in err_lower:
                cause = "assertion_failure"
                suggestion = "Check the expected vs actual values in the assertion"
            elif "importerror" in err_lower or "module" in err_lower:
                cause = "import_error"
                suggestion = "Verify the import path and that the module is installed"
            elif "timeout" in err_lower:
                cause = "timeout"
                suggestion = "Increase timeout or optimize test performance"
            elif "keyerror" in err_lower:
                cause = "missing_key"
                suggestion = "Check that the expected key exists in the data structure"
            elif "typeerror" in err_lower:
                cause = "type_error"
                suggestion = "Check function argument types and expected return types"
            elif "valueerror" in err_lower:
                cause = "value_error"
                suggestion = "Check input values for unexpected data"
            elif "attributeerror" in err_lower:
                cause = "attribute_error"
                suggestion = "Verify the object has the expected attribute or method"
            elif "zerodivisionerror" in err_lower:
                cause = "division_by_zero"
                suggestion = "Add a guard against zero values before division"
            elif "indexerror" in err_lower or "out of range" in err_lower:
                cause = "index_error"
                suggestion = "Check list/array bounds before accessing elements"
            analysis.append({"cause": cause, "suggestion": suggestion, "error_preview": err[:300]})

        return json.dumps({
            "method": "rule-based",
            "analysis": analysis,
            "failures_analyzed": len(errors),
            "note": "Install and configure LIKECODEX_LLM_API_URL/KEY for LLM-powered analysis",
        })
