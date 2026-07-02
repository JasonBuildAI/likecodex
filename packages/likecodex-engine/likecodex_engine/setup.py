"""Interactive setup wizard and diagnostics for LikeCodex.

Provides:
- interactive_setup(): Rich-based 3-step config wizard
- run_doctor(): Health check and diagnostics
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Confirm, Prompt
from rich.panel import Panel

from likecodex_engine.doctor import DiagnosisResult, Doctor

__all__ = [
    "interactive_setup",
    "run_doctor",
    "test_deepseek_connection",
    "Doctor",
    "DiagnosisResult",
]

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
    """Run diagnostics and health checks.

    Delegates to Doctor class from the doctor module.
    """
    doctor = Doctor()
    result = await doctor.diagnose()
    doctor.print_report(result)


if __name__ == "__main__":
    asyncio.run(interactive_setup())
