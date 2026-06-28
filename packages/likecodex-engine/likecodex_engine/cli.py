"""LikeCodex Python CLI - main entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
import urllib.request
import webbrowser
from pathlib import Path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="likecodex",
        description="LikeCodex - DeepSeek V4 native AI coding assistant",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Execute a one-shot task and exit",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Start interactive chat mode",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Start engine and open Web UI in browser",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("LIKECODEX_ENGINE_PORT", "9090")),
        help="Engine HTTP port (default: 9090)",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Connect directly to Python engine (skip Rust server)",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run interactive configuration wizard",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run diagnostics and health checks",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )
    return parser.parse_args(argv)


def _check_engine_running(port: int) -> bool:
    """Quick check if the engine is already running."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1):
            return True
    except Exception:
        return False


def main() -> None:
    """Main CLI entry point (installed via pyproject.toml [project.scripts])."""
    args = _parse_args()

    if args.version:
        from likecodex_engine import __version__

        print(f"LikeCodex v{__version__}")
        sys.exit(0)

    if args.setup:
        from likecodex_engine.setup import interactive_setup

        asyncio.run(interactive_setup())
        return

    if args.doctor:
        from likecodex_engine.setup import run_doctor

        asyncio.run(run_doctor())
        return

    if args.prompt:
        _run_one_shot(args.prompt, args.port)
        return

    if args.web:
        _run_web(args.port)
        return

    # Default: interactive chat
    _run_chat(args.port)


def _run_one_shot(prompt: str, port: int) -> None:
    """Run a single prompt via the engine API and print the result."""
    import httpx

    if not _check_engine_running(port):
        _start_engine_in_background(port)

    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=None) as client:
            response = client.post(
                "/run",
                json={"prompt": prompt, "session_id": "one-shot"},
            )
            result = response.json()
            print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _run_chat(port: int) -> None:
    """Interactive chat mode using the engine API."""
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console()

    if not _check_engine_running(port):
        console.print("[yellow]Engine not running. Starting...[/yellow]")
        _start_engine_in_background(port)

    session_id = _generate_session_id()
    console.print(
        f"[bold green]LikeCodex[/bold green] - DeepSeek V4 coding assistant"
    )
    console.print("Type 'exit' or 'quit' to end session.\n")

    import httpx

    with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=None) as client:
        while True:
            try:
                user_input = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                break

            # Stream the response
            try:
                with client.stream(
                    "POST",
                    "/chat",
                    json={
                        "prompt": user_input,
                        "session_id": session_id,
                        "stream": True,
                    },
                ) as response:
                    assistant_text = ""
                    for line in response.iter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            if data.get("type") == "delta" and data.get("content"):
                                assistant_text += data["content"]
                            elif data.get("type") == "message":
                                console.print()
                                console.print(
                                    Markdown(data.get("content", ""))
                                )
                        except json.JSONDecodeError:
                            pass

                    if assistant_text:
                        console.print(Markdown(assistant_text))
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                break


def _run_web(port: int) -> None:
    """Start engine and open Web UI."""
    from rich.console import Console

    console = Console()

    if not _check_engine_running(port):
        console.print("[yellow]Starting LikeCodex engine...[/yellow]")
        proc = _start_engine_in_background(port)
        time.sleep(2)

    url = f"http://127.0.0.1:{port}"
    console.print(f"[green]Opening Web UI at {url}[/green]")
    webbrowser.open(url)

    # Keep running
    console.print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\nShutting down...")


def _start_engine_in_background(port: int) -> None:
    """Start the Python engine as a subprocess."""
    engine_root = _find_engine_root()
    env = os.environ.copy()
    env.setdefault("LIKECODEX_ENGINE_PORT", str(port))

    proc = subprocess.Popen(
        [sys.executable, "-m", "likecodex_engine.server"],
        cwd=engine_root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait a bit for startup
    for _ in range(15):
        if _check_engine_running(port):
            return proc
        time.sleep(0.5)

    print("Warning: Engine may not have started in time.", file=sys.stderr)
    return proc


def _find_engine_root() -> str:
    """Find the project root directory (where pyproject.toml lives)."""
    # Check common locations
    candidates = [
        os.environ.get("LIKECODEX_ENGINE_ROOT"),
        os.environ.get("LIKECODEX_HOME"),
        str(Path.home() / ".likecodex" / "install"),
    ]

    for candidate in candidates:
        if candidate and Path(candidate).joinpath("pyproject.toml").exists():
            return candidate

    # Walk up from cwd
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if parent.joinpath("pyproject.toml").exists():
            return str(parent)

    return os.getcwd()


def _generate_session_id() -> str:
    return uuid.uuid4().hex[:12]


if __name__ == "__main__":
    main()
