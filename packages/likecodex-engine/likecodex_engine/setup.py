"""Interactive setup wizard and diagnostics for LikeCodex."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Confirm, Prompt
from rich.panel import Panel

console = Console()

CONFIG_TEMPLATE = """# LikeCodex configuration
# Auto-generated on {date}

[llm]
provider = "deepseek"
model = "{model}"
api_key = "{api_key}"

[approval]
mode = "{approval_mode}"

[agent]
enable_planner = {enable_planner}
"""

WELCOME = """# Welcome to LikeCodex!

LikeCodex is a DeepSeek V4 native AI coding assistant.

This quick setup will configure your API key and preferences (about 2 minutes).
"""

COMPLETION = """## Setup Complete!

You can now use LikeCodex:

  - **Interactive mode**: `likecodex --chat`
  - **One-shot task**: `likecodex "check my project's code quality"`
  - **Web interface**: `likecodex --web` (opens browser)

Need help? Run `likecodex --help`
"""


async def test_deepseek_connection(api_key: str) -> bool:
    """Test DeepSeek API connectivity."""
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        response = await client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        return bool(response.choices)
    except Exception as e:
        console.print(f"[dim]Connection test failed: {e}[/dim]")
        return False


async def interactive_setup() -> None:
    """Run the interactive configuration wizard."""
    console.print(Markdown(WELCOME))

    # Step 1: API Key
    console.print("\n[bold]Step 1/3: DeepSeek API Key[/bold]")
    console.print(
        "  Get your API key at [underline]https://platform.deepseek.com[/underline]"
    )

    api_key = Prompt.ask(
        "Enter your DeepSeek API Key",
        password=True,
    )

    if not api_key:
        console.print("[yellow]No API key provided. You'll need to configure it later.[/yellow]")
        api_key = ""
    elif not api_key.startswith("sk-"):
        console.print("[yellow]API keys usually start with 'sk-'. Please double-check.[/yellow]")
        if not Confirm.ask("Continue anyway?"):
            api_key = Prompt.ask("Re-enter your API Key", password=True)

    # Test connection
    if api_key:
        console.print("\n[bold]Testing API connection...[/bold]")
        if await test_deepseek_connection(api_key):
            console.print("[green]✓ API connection successful![/green]")
        else:
            console.print("[red]✗ Connection failed. Check your API key.[/red]")
            if not Confirm.ask("Ignore and continue?"):
                return

    # Step 2: Model selection
    console.print("\n[bold]Step 2/3: Choose default model[/bold]")
    console.print("  1) [green]deepseek-v4-flash[/green] - Fast & economical (recommended)")
    console.print("  2) [yellow]deepseek-v4-pro[/yellow]   - More capable, higher cost")

    model_choice = Prompt.ask("Choose (1 or 2)", default="1")
    model = "deepseek-v4-flash" if model_choice == "1" else "deepseek-v4-pro"

    # Step 3: Approval mode
    console.print("\n[bold]Step 3/3: Choose approval mode[/bold]")
    console.print("  1) [green]auto[/green]          - Auto-approve safe ops (recommended)")
    console.print("  2) [yellow]ask[/yellow]          - Ask before every write operation")
    console.print("  3) [red]full-access[/red]   - Trust everything (no approval)")
    console.print("  4) [blue]read-only[/blue]      - Read only, no modifications")

    approval_choice = Prompt.ask("Choose (1-4)", default="1")
    approval_map = {"1": "auto", "2": "ask", "3": "full-access", "4": "read-only"}
    approval_mode = approval_map.get(approval_choice, "auto")

    # Generate config
    config_dir = Path.home() / ".likecodex"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"

    from datetime import datetime

    config_content = CONFIG_TEMPLATE.format(
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        model=model,
        api_key=api_key,
        approval_mode=approval_mode,
        enable_planner="true",
    )

    # Mask API key in output
    safe_content = config_content.replace(api_key, "***") if api_key else config_content
    console.print(f"\nConfig will be saved to [cyan]{config_path}[/cyan]:")
    console.print(Panel(safe_content))

    if Confirm.ask("Save this configuration?", default=True):
        config_path.write_text(config_content, encoding="utf-8")
        console.print(f"[green]✓ Configuration saved to {config_path}[/green]")

    # Create project memory
    if Confirm.ask("\nCreate project memory file (.likecodex/memory.md)?", default=False):
        await _create_project_memory()

    console.print(Markdown(COMPLETION))


async def _create_project_memory() -> None:
    """Create a project memory file."""
    memory_dir = Path.cwd() / ".likecodex"
    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_path = memory_dir / "memory.md"

    content = f"""# Project Memory

Created: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}

## Project Overview
<!-- Describe what this project does -->

## Conventions
<!-- Coding conventions, patterns, preferences -->

## Architecture
<!-- Key architectural decisions -->
"""
    memory_path.write_text(content, encoding="utf-8")
    console.print(f"[green]✓ Created {memory_path}[/green]")


async def run_doctor() -> None:
    """Run diagnostics and health checks."""
    console.print("[bold]LikeCodex Diagnostics[/bold]\n")

    # 1. Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 11):
        console.print(f"[green]✓ Python {py_ver}[/green]")
    else:
        console.print(f"[red]✗ Python {py_ver} (need >= 3.11)[/red]")

    # 2. Config
    config_path = Path.home() / ".likecodex" / "config.toml"
    if config_path.exists():
        console.print(f"[green]✓ Config found at {config_path}[/green]")
        config_text = config_path.read_text(encoding="utf-8")
        # Mask API key
        for line in config_text.splitlines():
            if "api_key" in line.lower() and "=" in line:
                console.print(f"   {line.split('=')[0].strip()} = ***")
    else:
        console.print("[yellow]⚠ No config found. Run `likecodex --setup`[/yellow]")

    # 3. API key
    api_key = os.environ.get("DEEPSEEK_API_KEY") or ""
    if api_key:
        console.print(f"[green]✓ DEEPSEEK_API_KEY set ({api_key[:8]}...)[/green]")
    else:
        # Check config file
        if config_path.exists():
            cfg_text = config_path.read_text(encoding="utf-8")
            for line in cfg_text.splitlines():
                if "api_key" in line.lower() and "=" in line:
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        if api_key:
            console.print(f"[green]✓ API key found in config[/green]")
        else:
            console.print("[red]✗ No API key found[/red]")

    # 4. Engine status
    port = int(os.environ.get("LIKECODEX_ENGINE_PORT", "9090"))
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as resp:
            data = json.loads(resp.read().decode())
        console.print(f"[green]✓ Engine running on port {port}[/green]")
        if data.get("model"):
            console.print(f"   Model: {data['model']}")
    except Exception:
        console.print(f"[yellow]⚠ Engine not running on port {port}[/yellow]")

    # 5. System info
    import platform
    console.print(f"\n[bold]System:[/bold] {platform.system()} {platform.release()}")
    console.print(f"[bold]CWD:[/bold] {Path.cwd()}")


import json  # noqa: E402 (needed by run_doctor)


if __name__ == "__main__":
    asyncio.run(interactive_setup())
