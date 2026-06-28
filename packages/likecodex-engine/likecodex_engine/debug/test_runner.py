"""Test Runner Service — discovers and runs tests for multiple frameworks.

Supports:
- Python: pytest, unittest
- JavaScript/TypeScript: jest, vitest
- Rust: cargo test
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator


@dataclass
class TestCase:
    """A single test case."""

    id: str
    name: str
    file_path: str
    line: int = 0
    status: str = "pending"  # pending, running, passed, failed, skipped
    duration: float = 0.0
    error_message: str = ""
    error_stack: str = ""


@dataclass
class TestFile:
    """A test file containing test cases."""

    path: str
    framework: str = "unknown"
    tests: list[TestCase] = field(default_factory=list)


class TestRunnerService:
    """Discovers and runs tests."""

    def __init__(self, working_dir: str = ".") -> None:
        self.working_dir = str(Path(working_dir).resolve())

    async def discover_tests(self) -> dict[str, Any]:
        """Discover all test files and their test cases."""
        test_files: list[dict[str, Any]] = []

        # Python tests
        py_test_files = await self._discover_python_tests()
        test_files.extend(py_test_files)

        # JavaScript/TypeScript tests
        js_test_files = await self._discover_js_tests()
        test_files.extend(js_test_files)

        # Rust tests
        rs_test_files = await self._discover_rust_tests()
        test_files.extend(rs_test_files)

        return {"testFiles": test_files}

    async def _discover_python_tests(self) -> list[dict[str, Any]]:
        """Discover Python test files."""
        results: list[dict[str, Any]] = []
        test_patterns = ["test_*.py", "*_test.py", "tests.py"]

        for root, _dirs, files in os.walk(self.working_dir):
            # Skip common ignore directories
            if any(part in {"node_modules", ".venv", ".git", "__pycache__", ".pytest_cache"} for part in Path(root).parts):
                continue

            for fname in files:
                if not fname.endswith(".py"):
                    continue
                if not any(re.match(p.replace("*", ".*"), fname) for p in test_patterns):
                    continue

                rel_path = os.path.relpath(os.path.join(root, fname), self.working_dir)
                test_cases = await self._parse_python_test_cases(os.path.join(root, fname))

                results.append({
                    "path": rel_path.replace("\\", "/"),
                    "framework": "pytest",
                    "tests": test_cases,
                })

        return results

    @staticmethod
    async def _parse_python_test_cases(file_path: str) -> list[dict[str, Any]]:
        """Parse test function names from a Python test file."""
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, FileNotFoundError):
            return []

        test_cases: list[dict[str, Any]] = []
        lines = content.split("\n")

        for i, line in enumerate(lines):
            stripped = line.strip()
            # Match test functions: def test_*, async def test_*
            match = re.match(r"(?:async\s+)?def\s+(test_\w+)", stripped)
            if match:
                test_name = match.group(1)
                test_cases.append({
                    "id": f"{file_path}:{test_name}",
                    "name": test_name,
                    "filePath": os.path.relpath(file_path, os.getcwd()).replace("\\", "/"),
                    "line": i + 1,
                    "status": "pending",
                })

        return test_cases

    async def _discover_js_tests(self) -> list[dict[str, Any]]:
        """Discover JavaScript/TypeScript test files."""
        results: list[dict[str, Any]] = []
        test_patterns = [r".*\.test\.(ts|tsx|js|jsx)$", r".*\.spec\.(ts|tsx|js|jsx)$"]

        for root, _dirs, files in os.walk(self.working_dir):
            if any(part in {"node_modules", ".git", ".next"} for part in Path(root).parts):
                continue

            for fname in files:
                if not any(re.match(p, fname) for p in test_patterns):
                    continue

                rel_path = os.path.relpath(os.path.join(root, fname), self.working_dir)
                framework = "vitest" if os.path.exists(os.path.join(self.working_dir, "vitest.config.ts")) or os.path.exists(os.path.join(self.working_dir, "vitest.config.js")) else "jest"

                test_cases = await self._parse_js_test_cases(os.path.join(root, fname))

                results.append({
                    "path": rel_path.replace("\\", "/"),
                    "framework": framework,
                    "tests": test_cases,
                })

        return results

    @staticmethod
    async def _parse_js_test_cases(file_path: str) -> list[dict[str, Any]]:
        """Parse test names from a JS/TS test file."""
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, FileNotFoundError):
            return []

        test_cases: list[dict[str, Any]] = []
        lines = content.split("\n")

        for i, line in enumerate(lines):
            stripped = line.strip()
            # Match: test("name", ...) or it("name", ...) or describe("name", ...)
            match = re.match(r'(?:test|it)\s*\(\s*["\']([^"\']+)["\']', stripped)
            if match:
                test_name = match.group(1)
                test_cases.append({
                    "id": f"{file_path}:{test_name}",
                    "name": test_name,
                    "filePath": os.path.relpath(file_path, os.getcwd()).replace("\\", "/"),
                    "line": i + 1,
                    "status": "pending",
                })

        return test_cases

    async def _discover_rust_tests(self) -> list[dict[str, Any]]:
        """Discover Rust test files."""
        results: list[dict[str, Any]] = []
        cargo_toml = os.path.join(self.working_dir, "Cargo.toml")
        if not os.path.exists(cargo_toml):
            return results

        for root, _dirs, files in os.walk(self.working_dir):
            if any(part in {"target", ".git"} for part in Path(root).parts):
                continue

            for fname in files:
                if not fname.endswith(".rs"):
                    continue

                try:
                    with open(os.path.join(root, fname), encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except (OSError, FileNotFoundError):
                    continue

                test_cases: list[dict[str, Any]] = []
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if re.search(r"#\[test\]", line.strip()):
                        # Next line should be the test function
                        if i + 1 < len(lines):
                            match = re.match(r"\s*(?:pub\s+)?fn\s+(\w+)", lines[i + 1])
                            if match:
                                test_name = match.group(1)
                                rel_path = os.path.relpath(os.path.join(root, fname), self.working_dir).replace("\\", "/")
                                test_cases.append({
                                    "id": f"{rel_path}:{test_name}",
                                    "name": test_name,
                                    "filePath": rel_path,
                                    "line": i + 2,
                                    "status": "pending",
                                })

                if test_cases:
                    rel_path = os.path.relpath(os.path.join(root, fname), self.working_dir).replace("\\", "/")
                    results.append({
                        "path": rel_path,
                        "framework": "cargo-test",
                        "tests": test_cases,
                    })

        return results

    async def run_tests(self, test_filter: str = "") -> AsyncGenerator[dict, None]:
        """Run tests and yield SSE events.

        Events:
        - {"type": "start", "count": N}
        - {"type": "test_start", "testId": "...", "name": "..."}
        - {"type": "test_result", "testId": "...", "status": "passed/failed", "duration": N, "error": "..."}
        - {"type": "done", "passed": N, "failed": N, "total": N}
        """
        discovery = await self.discover_tests()
        all_tests: list[dict[str, Any]] = []

        for tf in discovery["testFiles"]:
            all_tests.extend(tf["tests"])

        if test_filter:
            all_tests = [t for t in all_tests if test_filter.lower() in t["name"].lower()]

        yield {"type": "start", "count": len(all_tests)}

        passed = 0
        failed = 0

        for test in all_tests:
            yield {"type": "test_start", "testId": test["id"], "name": test["name"]}

            # Determine framework and run
            file_path = test["filePath"]
            if file_path.endswith(".py"):
                result = await self._run_python_test(file_path, test["name"])
            elif file_path.endswith((".ts", ".tsx", ".js", ".jsx")):
                result = await self._run_js_test(file_path, test["name"])
            elif file_path.endswith(".rs"):
                result = await self._run_rust_test(file_path, test["name"])
            else:
                result = {"status": "skipped", "duration": 0, "error": "Unsupported file type"}

            if result["status"] == "passed":
                passed += 1
            elif result["status"] == "failed":
                failed += 1

            yield {
                "type": "test_result",
                "testId": test["id"],
                "status": result["status"],
                "duration": result["duration"],
                "error": result.get("error", ""),
                "stack": result.get("stack", ""),
            }

        yield {"type": "done", "passed": passed, "failed": failed, "total": len(all_tests)}

    async def _run_subprocess_test(self, cmd: list[str]) -> dict[str, Any]:
        """Run a test command via subprocess and return the result."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")

            if proc.returncode == 0:
                return {"status": "passed", "duration": 0, "output": output}
            return {
                "status": "failed",
                "duration": 0,
                "error": error or output,
                "stack": error,
            }
        except Exception as exc:
            return {"status": "failed", "duration": 0, "error": str(exc)}

    async def _run_python_test(self, file_path: str, test_name: str) -> dict[str, Any]:
        """Run a single Python test."""
        return await self._run_subprocess_test([
            sys.executable, "-m", "pytest",
            f"{file_path}::{test_name}",
            "-v", "--no-header", "--tb=short", "-q",
        ])

    async def _run_js_test(self, file_path: str, test_name: str) -> dict[str, Any]:
        """Run a single JS/TS test."""
        npx = "npx.cmd" if sys.platform == "win32" else "npx"
        return await self._run_subprocess_test([
            npx, "vitest", "run", file_path, "-t", test_name, "--reporter=verbose",
        ])

    async def _run_rust_test(self, file_path: str, test_name: str) -> dict[str, Any]:
        """Run a single Rust test."""
        return await self._run_subprocess_test([
            "cargo", "test", test_name, "--", "--exact", "--nocapture",
        ])
