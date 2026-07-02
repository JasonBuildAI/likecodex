"""Test discovery and execution tools for the agent.

Phase 7.16: Test Coverage Visualization
- Coverage collection (coverage.py for Python, basic for others)
- Coverage summary per file
- Line-by-line coverage data
- Export to LCOV format
"""

from __future__ import annotations

import asyncio
import json
import os
import re
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

    # ── Coverage ────────────────────────────────────────────────────────

    def collect_coverage_schema(self) -> dict[str, Any]:
        return {
            "description": "Run test coverage analysis and return coverage data per file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_dir": {
                        "type": "string",
                        "description": "Source directory to measure coverage for (relative to working dir)",
                        "default": ".",
                    },
                    "test_filter": {
                        "type": "string",
                        "description": "Optional test filter",
                        "default": "",
                    },
                },
            },
        }

    async def collect_coverage(self, source_dir: str = ".", test_filter: str = "") -> str:
        """Collect test coverage using coverage.py (for Python projects)."""
        src_path = (self.working_dir / source_dir).resolve()

        # Try pytest-cov or coverage.py
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable or "python",
                "-m", "coverage", "run",
                "--source", str(src_path),
                "-m", "pytest",
                *(["-k", test_filter] if test_filter else []),
                cwd=self.working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300.0)
            exit_code = proc.returncode
        except (TimeoutError, FileNotFoundError):
            # Fallback: try just running pytest directly
            return json.dumps({
                "error": "coverage.py not available",
                "hint": "Install coverage.py: pip install coverage",
            })

        if not (self.working_dir / ".coverage").exists():
            return json.dumps({
                "error": "Coverage data file not created",
                "exit_code": exit_code,
                "stdout": stdout.decode("utf-8", errors="replace")[:500],
                "stderr": stderr.decode("utf-8", errors="replace")[:500],
            })

        # Get coverage report as JSON
        try:
            report_proc = await asyncio.create_subprocess_exec(
                sys.executable or "python",
                "-m", "coverage", "json",
                cwd=self.working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(report_proc.communicate(), timeout=30.0)

            report_path = self.working_dir / "coverage.json"
            if report_path.exists():
                data = json.loads(report_path.read_text(encoding="utf-8"))
                report_path.unlink(missing_ok=True)
                return json.dumps(self._format_coverage(data, src_path))
        except Exception as e:
            return json.dumps({"error": f"Failed to parse coverage: {e}"})

        return json.dumps({"error": "Unknown coverage error"})

    def _format_coverage(self, data: dict, src_path: Path) -> dict:
        """Convert coverage.py JSON output to a friendly format."""
        meta = data.get("meta", {})
        files_data = data.get("files", {})

        formatted_files = []
        total_lines = 0
        covered_lines = 0

        for file_path, file_info in files_data.items():
            abs_path = Path(file_path)
            try:
                rel_path = str(abs_path.relative_to(self.working_dir))
            except ValueError:
                rel_path = file_path

            executed = file_info.get("executed_lines", [])
            missing = file_info.get("missing_lines", [])
            summary = file_info.get("summary", {})

            file_total = summary.get("num_lines", 0)
            file_covered = summary.get("covered_lines", 0)
            file_percent = summary.get("percent_covered", 0.0) if file_total > 0 else 0.0

            total_lines += file_total
            covered_lines += file_covered

            # Line-by-line coverage
            all_lines_set = set(executed) | set(missing)
            line_details = []
            for ln in sorted(all_lines_set):
                line_details.append({
                    "line": ln,
                    "covered": ln in executed,
                })

            formatted_files.append({
                "file": rel_path,
                "total_lines": file_total,
                "covered_lines": file_covered,
                "missed_lines": len(missing),
                "coverage_percent": round(file_percent, 1),
                "lines": line_details,
            })

        formatted_files.sort(key=lambda f: f["file"])
        overall_percent = round((covered_lines / total_lines * 100) if total_lines > 0 else 0.0, 1)

        return {
            "source_dir": str(src_path.relative_to(self.working_dir)),
            "overall": {
                "total_lines": total_lines,
                "covered_lines": covered_lines,
                "missed_lines": total_lines - covered_lines,
                "coverage_percent": overall_percent,
            },
            "files": formatted_files,
            "file_count": len(formatted_files),
        }

    def coverage_lcov_schema(self) -> dict[str, Any]:
        return {
            "description": "Export test coverage data to LCOV format.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_dir": {
                        "type": "string",
                        "description": "Source directory to measure coverage for",
                        "default": ".",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to write LCOV file (relative to working dir)",
                        "default": "coverage.lcov",
                    },
                },
            },
        }

    async def coverage_lcov(self, source_dir: str = ".", output_path: str = "coverage.lcov") -> str:
        """Export coverage data to LCOV format."""
        # First collect coverage
        coverage_result = await self.collect_coverage(source_dir=source_dir)
        try:
            data = json.loads(coverage_result)
        except json.JSONDecodeError:
            return json.dumps({"error": "Failed to collect coverage data first"})

        if "error" in data:
            return coverage_result

        # Generate LCOV
        lcov_lines = []
        out_path = self.working_dir / output_path

        for file_info in data.get("files", []):
            rel_path = file_info["file"]
            lcov_lines.append(f"SF:{rel_path}")
            for line_info in file_info.get("lines", []):
                ln = line_info["line"]
                count = 1 if line_info["covered"] else 0
                lcov_lines.append(f"DA:{ln},{count}")
            lcov_lines.append(f"end_of_record")

        lcov_content = "\n".join(lcov_lines)
        out_path.write_text(lcov_content, encoding="utf-8")

        # Clean up coverage artifacts
        cov_db = self.working_dir / ".coverage"
        if cov_db.exists():
            cov_db.unlink(missing_ok=True)

        return json.dumps({
            "output_path": str(out_path.relative_to(self.working_dir)),
            "file_count": data.get("file_count", 0),
            "overall": data.get("overall", {}),
            "lcov_size": len(lcov_content),
        })

    def coverage_summary_schema(self) -> dict[str, Any]:
        return {
            "description": "Get a quick text summary of test coverage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_dir": {
                        "type": "string",
                        "description": "Source directory to measure coverage for",
                        "default": ".",
                    },
                },
            },
        }

    async def coverage_summary(self, source_dir: str = ".") -> str:
        """Get a quick text summary of coverage for display."""
        result = await self.collect_coverage(source_dir=source_dir)
        try:
            data = json.loads(result)
        except json.JSONDecodeError:
            return json.dumps({"error": "Coverage collection failed"})

        if "error" in data:
            return result

        overall = data.get("overall", {})
        files = data.get("files", [])

        text_lines = [
            f"Coverage: {overall.get('coverage_percent', 0)}%",
            f"Files: {data.get('file_count', 0)}",
            f"Total lines: {overall.get('total_lines', 0)}",
            f"Covered: {overall.get('covered_lines', 0)}",
            f"Missed: {overall.get('missed_lines', 0)}",
            "",
            "Per file:",
        ]

        for f in files[:20]:
            bar = "█" * int(f["coverage_percent"] / 5) + "░" * (20 - int(f["coverage_percent"] / 5))
            text_lines.append(f"  {f['coverage_percent']:5.1f}% {bar} {f['file']}")

        if len(files) > 20:
            text_lines.append(f"  ... and {len(files) - 20} more files")

        return json.dumps({
            "summary": "\n".join(text_lines),
            "data": data,
        })

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
