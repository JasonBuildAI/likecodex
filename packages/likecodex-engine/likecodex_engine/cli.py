"""LikeCodex Python CLI - main entry point.

Usage:
    likecodex                              # Interactive chat mode (default)
    likecodex "prompt text"                # One-shot task execution
    likecodex --chat                       # Interactive chat mode
    likecodex --web                        # Start engine and open Web UI
    likecodex --mode agent "task"          # Agent mode
    likecodex --model pro "complex task"   # Use pro model
    echo "hello" | likecodex               # Stdin pipe support
    likecodex "task" --json               # JSON output
"""

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
        description=(
            "LikeCodex - DeepSeek V4 native AI coding assistant\n\n"
            "LikeCodex is an open-source coding agent powered by DeepSeek V4.\n"
            "Describe a task in natural language; the agent reads your codebase,\n"
            "runs commands, edits files, and reports back."
        ),
        epilog=(
            "Examples:\n"
            "  likecodex                               Start interactive chat\n"
            "  likecodex 'fix this bug'                 One-shot task\n"
            "  likecodex --mode agent 'refactor'        Agent mode\n"
            "  likecodex --model pro 'complex task'     Use pro model\n"
            "  echo 'hello' | likecodex                Stdin pipe\n"
            "  likecodex --json 'task'                  JSON output format\n"
            "  likecodex --setup                        Configuration wizard\n"
            "  likecodex --doctor                       Health diagnostics\n"
            "  likecodex --web                          Start engine + open browser\n"
            "\n"
            "Modes:\n"
            "  ask       Read-only Q&A - AI answers without modifications\n"
            "  agent     Auto-execute - AI reads, writes, runs autonomously\n"
            "  manual    Step-by-step - each action requires confirmation\n"
            "\n"
            "Models:\n"
            "  flash     DeepSeek V4 Flash (fast, economical)\n"
            "  pro       DeepSeek V4 Pro (more capable, slower)\n"
            "\n"
            "Documentation: https://github.com/JasonBuildAI/likecodex\n"
            "Issues: https://github.com/JasonBuildAI/likecodex/issues"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Execute a one-shot task and exit (or pipe input via stdin)",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Start interactive chat mode (default when no prompt given)",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Start engine server and open Web UI in browser",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("LIKECODEX_ENGINE_PORT", "9090")),
        help="Engine HTTP port (default: 9090, env: LIKECODEX_ENGINE_PORT)",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Connect directly to Python engine (skip Rust server)",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run interactive configuration wizard (API key, config, project memory)",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run environment diagnostics and health checks",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version information and exit",
    )
    parser.add_argument(
        "--mode",
        choices=["ask", "agent", "manual"],
        default=None,
        help="Working mode: ask (prompt before actions), agent (autonomous), manual (step-by-step)",
    )
    parser.add_argument(
        "--model",
        choices=["flash", "pro"],
        default=None,
        help="Model selection: flash (fast/economical) or pro (more capable, slower)",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Output results in JSON format (machine-readable)",
    )
    parser.add_argument(
        "--plain",
        dest="output_plain",
        action="store_true",
        help="Output results in plain text (disable Rich formatting)",
    )
    return parser.parse_args(argv)


def _check_engine_running(port: int) -> bool:
    """Quick check if the engine is already running."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1):
            return True
    except Exception:
        return False


def _read_stdin() -> str | None:
    """Read prompt from stdin if piped (non-interactive)."""
    if not sys.stdin.isatty():
        try:
            return sys.stdin.read().strip()
        except Exception:
            return None
    return None


def main() -> None:
    """Main CLI entry point (installed via pyproject.toml [project.scripts])."""
    args = _parse_args()

    # ── Version ──
    if args.version:
        from likecodex_engine import __version__

        print(f"LikeCodex v{__version__}")
        sys.exit(0)

    # ── Setup wizard ──
    if args.setup:
        from likecodex_engine.setup import interactive_setup

        asyncio.run(interactive_setup())
        return

    # ── Doctor / diagnostics ──
    if args.doctor:
        from likecodex_engine.setup import run_doctor

        asyncio.run(run_doctor())
        return

    # ── Resolve prompt (from arg or stdin pipe) ──
    prompt = args.prompt
    if not prompt:
        stdin_prompt = _read_stdin()
        if stdin_prompt:
            prompt = stdin_prompt

    # ── Build runtime config with mode/model overrides ──
    runtime_config = {}
    if args.mode:
        runtime_config["approval_mode"] = {
            "ask": "ask",
            "agent": "auto",
            "manual": "manual",
        }.get(args.mode, "auto")
    if args.model:
        runtime_config["model"] = f"deepseek-v4-{args.model}"

    if prompt:
        _run_one_shot(prompt, args.port, runtime_config, args.output_json, args.output_plain)
        return

    if args.web:
        _run_web(args.port)
        return

    # Default: interactive chat
    _run_chat(args.port, args.output_plain)


def _run_one_shot(
    prompt: str,
    port: int,
    config_override: dict | None = None,
    output_json: bool = False,
    output_plain: bool = False,
) -> None:
    """Run a single prompt via the engine API and print the result."""
    import httpx

    if not _check_engine_running(port):
        _start_engine_in_background(port)

    payload: dict = {"prompt": prompt, "session_id": "one-shot"}
    if config_override:
        payload.update(config_override)

    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=None) as client:
            response = client.post("/run", json=payload)
            response.raise_for_status()
            result = response.json()

            if output_json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                content = result.get("content", result.get("response", str(result)))
                print(content)
    except httpx.HTTPStatusError as e:
        print(f"[error] Server returned {e.response.status_code}: {e.response.text[:500]}", file=sys.stderr)
        sys.exit(1)
    except httpx.RequestError as e:
        print(f"[error] Cannot connect to engine at 127.0.0.1:{port}: {e}", file=sys.stderr)
        print(f"[hint]  Start the engine with: likecodex --web  or  likecodex --chat", file=sys.stderr)
        sys.exit(1)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"[error] Invalid response from engine: {e}", file=sys.stderr)
        sys.exit(1)


def _run_chat(port: int, output_plain: bool = False) -> None:
    """Interactive chat mode using the engine API."""
    if output_plain:
        _run_chat_plain(port)
    else:
        _run_chat_rich(port)


def _run_chat_plain(port: int) -> None:
    """Simple text-based interactive chat."""
    if not _check_engine_running(port):
        print("Engine not running. Starting...")
        _start_engine_in_background(port)

    session_id = _generate_session_id()
    print("LikeCodex - DeepSeek V4 coding assistant")
    print("Type 'exit' or 'quit' to end session.\n")

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
                    for line in response.iter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            if data.get("type") == "delta" and data.get("content"):
                                print(data["content"], end="", flush=True)
                            elif data.get("type") == "message":
                                print()
                                print(data.get("content", ""))
                        except json.JSONDecodeError:
                            pass
                    print()
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                break


def _run_chat_rich(port: int) -> None:
    """Rich-formatted interactive chat using the engine API."""
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
        _start_engine_in_background(port)
        time.sleep(2)

    url = f"http://127.0.0.1:{port}"
    console.print(f"[green]Opening Web UI at {url}[/green]")
    webbrowser.open(url)

    console.print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\nShutting down...")


def _start_engine_in_background(port: int) -> subprocess.Popen | None:
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
    for candidate in (
        os.environ.get("LIKECODEX_ENGINE_ROOT"),
        os.environ.get("LIKECODEX_HOME"),
        str(Path.home() / ".likecodex" / "install"),
    ):
        if candidate and Path(candidate).joinpath("pyproject.toml").exists():
            return candidate

    cwd = Path.cwd()
    for parent in (cwd, *cwd.parents):
        if parent.joinpath("pyproject.toml").exists():
            return str(parent)

    return os.getcwd()


def _generate_session_id() -> str:
    return uuid.uuid4().hex[:12]


if __name__ == "__main__":
    main()
