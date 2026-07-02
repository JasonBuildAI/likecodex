"""Environment diagnostics module for LikeCodex.

Provides structured health checks for the runtime environment:
- Python version, Git, Docker, Node.js, Rust toolchain
- DeepSeek API connectivity test
- Output formatting (terminal / JSON)

Usage:
    doctor = Doctor()
    result = await doctor.diagnose()
    doctor.print_report(result)
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

__all__ = [
    "Doctor",
    "DiagnosisResult",
]

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DiagnosisResult:
    """Structured result of a full environment diagnosis."""

    timestamp: str = ""
    python_version: str = ""
    python_ok: bool = False
    git_available: bool = False
    git_version: str = ""
    docker_available: bool = False
    node_available: bool = False
    node_version: str = ""
    rust_available: bool = False
    cargo_available: bool = False
    deepseek_api_reachable: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "python": {
                "version": self.python_version,
                "ok": self.python_ok,
            },
            "git": {
                "available": self.git_available,
                "version": self.git_version,
            },
            "docker": {
                "available": self.docker_available,
            },
            "node": {
                "available": self.node_available,
                "version": self.node_version,
            },
            "rust": {
                "available": self.rust_available,
                "cargo_available": self.cargo_available,
            },
            "deepseek_api": {
                "reachable": self.deepseek_api_reachable,
            },
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------


class Doctor:
    """Environment health diagnostics.

    Each check is a separate method so subclasses can override individual
    checks for testing or customisation.
    """

    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/models"

    # ── Public API ──────────────────────────────────────────────────────

    async def diagnose(self) -> DiagnosisResult:
        """Run all health checks and return a structured result."""
        result = DiagnosisResult(
            timestamp=datetime.now().isoformat(),
        )
        result.python_version = self._check_python(result)
        self._check_git(result)
        self._check_docker(result)
        self._check_node(result)
        self._check_rust(result)
        await self._check_deepseek_api(result)
        return result

    def print_report(self, result: DiagnosisResult, *, json_output: bool = False) -> None:
        """Print the diagnosis report to stdout.

        Args:
            result: The diagnosis result to print.
            json_output: If True, print as JSON instead of human-readable.
        """
        if json_output:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
            return

        from rich.console import Console
        from rich.table import Table

        console = Console()

        # ── Summary header ──────────────────────────────────────────────
        console.print()
        console.print("[bold cyan]LikeCodex Environment Diagnostics[/bold cyan]")
        console.print(f"  Timestamp: {result.timestamp}")
        console.print()

        # ── Checks table ────────────────────────────────────────────────
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Status", style="bold", width=4)
        table.add_column("Check")
        table.add_column("Detail", style="dim")

        def add_check(ok: bool, label: str, detail: str = "") -> None:
            icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
            table.add_row(icon, label, detail)

        add_check(result.python_ok, "Python", result.python_version)
        add_check(result.git_available, "Git", result.git_version)
        add_check(result.docker_available, "Docker", "")
        add_check(result.node_available, "Node.js", result.node_version)
        add_check(result.rust_available, "Rust", "rustc available")
        add_check(result.cargo_available, "Cargo", "cargo available")
        add_check(result.deepseek_api_reachable, "DeepSeek API", "")

        console.print(table)
        console.print()

        # ── Errors & warnings ───────────────────────────────────────────
        for err in result.errors:
            console.print(f"  [red]✗ {err}[/red]")
        for warn in result.warnings:
            console.print(f"  [yellow]⚠ {warn}[/yellow]")
        if not result.errors and not result.warnings:
            console.print("  [green]All checks passed.[/green]")
        console.print()

    # ── Individual checks ───────────────────────────────────────────────

    def _check_python(self, result: DiagnosisResult) -> str:
        version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        result.python_version = version
        result.python_ok = sys.version_info >= (3, 11)
        if not result.python_ok:
            result.errors.append(
                f"Python {version} is too old. LikeCodex requires >= 3.11."
            )
        return version

    def _check_git(self, result: DiagnosisResult) -> None:
        git_path = shutil.which("git")
        if not git_path:
            result.warnings.append("Git not found on PATH.")
            return

        result.git_available = True
        try:
            output = subprocess.run(
                [git_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            result.git_version = output.stdout.strip()
        except (subprocess.SubprocessError, OSError) as exc:
            result.errors.append(f"Git version check failed: {exc}")

    def _check_docker(self, result: DiagnosisResult) -> None:
        docker_path = shutil.which("docker")
        if not docker_path:
            result.warnings.append("Docker not found on PATH (optional for sandbox).")
            return

        try:
            subprocess.run(
                [docker_path, "info"],
                capture_output=True,
                timeout=10,
            )
            result.docker_available = True
        except (subprocess.SubprocessError, OSError):
            result.warnings.append("Docker found but daemon may not be running.")

    def _check_node(self, result: DiagnosisResult) -> None:
        node_path = shutil.which("node")
        if not node_path:
            result.warnings.append("Node.js not found on PATH (optional for Web UI).")
            return

        result.node_available = True
        try:
            output = subprocess.run(
                [node_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            result.node_version = output.stdout.strip()
        except (subprocess.SubprocessError, OSError) as exc:
            result.errors.append(f"Node.js version check failed: {exc}")

    def _check_rust(self, result: DiagnosisResult) -> None:
        rustc_path = shutil.which("rustc")
        if not rustc_path:
            result.warnings.append("Rust toolchain not found on PATH (optional).")
            return

        result.rust_available = True
        result.cargo_available = shutil.which("cargo") is not None

    async def _check_deepseek_api(self, result: DiagnosisResult) -> None:
        """Check DeepSeek API reachability via an HTTPS GET."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    self.DEEPSEEK_API_URL,
                    headers={
                        "Accept": "application/json",
                    },
                )
                # If we get any HTTP response (even 401/403), the host is reachable.
                result.deepseek_api_reachable = resp.status_code < 500
        except (httpx.HTTPError, ImportError, OSError) as exc:
            result.deepseek_api_reachable = False
            result.warnings.append(f"DeepSeek API unreachable: {exc}")
