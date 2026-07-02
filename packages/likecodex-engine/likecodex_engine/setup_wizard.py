"""Interactive setup wizard for LikeCodex first-time configuration.

Provides a rich terminal wizard that guides the user through:
1. LLM provider selection (DeepSeek / OpenAI / offline Mock)
2. API key input (for online providers)
3. Agent mode selection (auto / manual / approve)
4. Optional component installation

Writes configuration to ~/.likecodex/config.toml.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

__all__ = [
    "interactive_setup",
    "run_setup_wizard",
]

console = Console()

WELCOME_MD = """# Welcome to LikeCodex!

LikeCodex is a DeepSeek V4 native AI coding assistant.

This wizard will help you configure LikeCodex in 4 quick steps (about 2 minutes).
"""

COMPLETION_MD = """## Setup Complete!

You can now use LikeCodex:

  - **Interactive mode**: `likecodex --chat`
  - **One-shot task**: `likecodex` + your task description
  - **Web interface**: `likecodex --web` (opens browser)

Need help? Run `likecodex --help`
"""

PROVIDER_OPTIONS: dict[str, dict[str, str]] = {
    "1": {
        "name": "DeepSeek",
        "description": "DeepSeek V4 Flash / Pro (recommended)",
        "base_url": "https://api.deepseek.com",
    },
    "2": {
        "name": "OpenAI",
        "description": "OpenAI GPT-4o / o3 (requires API key)",
        "base_url": "https://api.openai.com/v1",
    },
    "3": {
        "name": "Offline Mock",
        "description": "Local mock provider (no API key needed, for testing)",
        "base_url": "",
    },
}

MODE_OPTIONS: dict[str, str] = {
    "1": "auto",
    "2": "manual",
    "3": "approve",
}

OPTIONAL_COMPONENTS: dict[str, str] = {
    "sandbox": "Docker sandbox for safe command execution",
    "memory": "Vector memory with ChromaDB for long-term context",
    "webui": "Web UI (requires Node.js for frontend build)",
}


async def interactive_setup() -> None:
    """Alias for run_setup_wizard, kept for backward compatibility."""
    await run_setup_wizard()


async def run_setup_wizard() -> None:
    """Run the interactive 4-step configuration wizard."""
    console.print(Markdown(WELCOME_MD))

    # ── Step 1: LLM Provider ──────────────────────────────────────
    config = await _step_provider_selection()
    if config is None:
        return

    # ── Step 2: API Key ───────────────────────────────────────────
    if config.get("online", True):
        await _step_api_key(config)
        if config.get("api_key"):
            await _test_connection(config)

    # ── Step 3: Agent Mode ────────────────────────────────────────
    await _step_agent_mode(config)

    # ── Step 4: Optional Components ───────────────────────────────
    await _step_optional_components(config)

    # ── Write config ──────────────────────────────────────────────
    config_dir = Path.home() / ".likecodex"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"

    config_content = _render_config_toml(config)
    safe_content = _mask_api_key(config_content, config.get("api_key", ""))

    console.print(f"\nConfig will be saved to [cyan]{config_path}[/cyan]:")
    console.print(Panel(safe_content))

    if Confirm.ask("Save this configuration?", default=True):
        config_path.write_text(config_content, encoding="utf-8")
        console.print(f"[green]✓ Configuration saved to {config_path}[/green]")

    # ── Create project memory ─────────────────────────────────────
    if Confirm.ask("\nCreate project memory file (.likecodex/memory.md)?", default=False):
        await _create_project_memory()

    console.print(Markdown(COMPLETION_MD))


# ---------------------------------------------------------------------------
# Step helpers
# ---------------------------------------------------------------------------


async def _step_provider_selection() -> dict[str, Any] | None:
    """Step 1: Let user choose an LLM provider."""
    console.print("\n[bold]Step 1/4: Choose LLM Provider[/bold]\n")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key")
    table.add_column("Provider")
    table.add_column("Description", style="dim")
    for key, info in PROVIDER_OPTIONS.items():
        table.add_row(f"  {key})", f"[green]{info['name']}[/green]", info["description"])
    console.print(table)

    choice = Prompt.ask("Choose (1-3)", default="1")
    if choice not in PROVIDER_OPTIONS:
        console.print("[red]Invalid choice. Using DeepSeek as default.[/red]")
        choice = "1"

    info = PROVIDER_OPTIONS[choice]
    is_online = choice != "3"
    config: dict[str, Any] = {
        "provider": info["name"].lower().replace(" ", "-"),
        "provider_name": info["name"],
        "base_url": info["base_url"],
        "online": is_online,
        "api_key": "",
        "model": {
            "1": "deepseek-v4-flash",
            "2": "gpt-4o",
            "3": "mock-model",
        }.get(choice, "deepseek-v4-flash"),
        "approval_mode": "auto",
        "enable_planner": True,
        "optional_components": [],
    }

    console.print(f"[green]✓ Selected {info['name']}[/green]")
    return config


async def _step_api_key(config: dict[str, Any]) -> None:
    """Step 2: Collect API key."""
    console.print("\n[bold]Step 2/4: API Key[/bold]")
    provider = config["provider_name"]
    console.print(f"  Enter your {provider} API key.")
    if provider == "DeepSeek":
        console.print("  Get your key at [underline]https://platform.deepseek.com[/underline]")
    elif provider == "OpenAI":
        console.print("  Get your key at [underline]https://platform.openai.com/api-keys[/underline]")

    api_key = Prompt.ask("API Key", password=True)
    if not api_key:
        console.print("[yellow]No API key provided. You can configure it later.[/yellow]")
        api_key = ""

    config["api_key"] = api_key

    # Validate format
    if api_key and provider == "DeepSeek" and not api_key.startswith("sk-"):
        console.print("[yellow]DeepSeek API keys usually start with 'sk-'. Please double-check.[/yellow]")
        if not Confirm.ask("Continue anyway?"):
            config["api_key"] = Prompt.ask("Re-enter your API Key", password=True)


async def _test_connection(config: dict[str, Any]) -> None:
    """Test API connectivity for the chosen provider."""
    console.print("\n[bold]Testing API connection...[/bold]")
    ok = await _test_api_connectivity(
        provider=config["provider"],
        api_key=config.get("api_key", ""),
        base_url=config.get("base_url", ""),
    )
    if ok:
        console.print("[green]✓ API connection successful![/green]")
    else:
        console.print("[red]✗ Connection failed. Check your API key and network.[/red]")
        if not Confirm.ask("Ignore and continue?"):
            config["api_key"] = ""
            config["online"] = False


async def _step_agent_mode(config: dict[str, Any]) -> None:
    """Step 3: Choose agent approval mode."""
    console.print("\n[bold]Step 3/4: Choose Agent Mode[/bold]\n")

    mode_table = Table(show_header=False, box=None, padding=(0, 2))
    mode_table.add_column("Key")
    mode_table.add_column("Mode")
    mode_table.add_column("Description", style="dim")
    mode_table.add_row("  1)", "[green]auto[/green]", "Auto-approve safe operations")
    mode_table.add_row("  2)", "[yellow]manual[/yellow]", "Step-by-step confirmation")
    mode_table.add_row("  3)", "[blue]approve[/blue]", "Ask before every write operation")
    console.print(mode_table)

    choice = Prompt.ask("Choose (1-3)", default="1")
    config["approval_mode"] = MODE_OPTIONS.get(choice, "auto")

    console.print(f"[green]✓ Mode set to '{config['approval_mode']}'[/green]")

    # Planner sub-question
    if Confirm.ask("Enable smart planning for complex tasks?", default=True):
        config["enable_planner"] = True
    else:
        config["enable_planner"] = False


async def _step_optional_components(config: dict[str, Any]) -> None:
    """Step 4: Select optional components to install."""
    console.print("\n[bold]Step 4/4: Optional Components[/bold]\n")

    selected: list[str] = []
    for key, desc in OPTIONAL_COMPONENTS.items():
        if Confirm.ask(f"Install [cyan]{key}[/cyan]? ({desc})", default=False):
            selected.append(key)

    config["optional_components"] = selected
    if selected:
        console.print(f"[green]✓ Selected: {', '.join(selected)}[/green]")
    else:
        console.print("[dim]No optional components selected.[/dim]")


# ---------------------------------------------------------------------------
# Config rendering
# ---------------------------------------------------------------------------


def _render_config_toml(config: dict[str, Any]) -> str:
    """Render the configuration dictionary as a TOML string."""
    api_key = config.get("api_key", "")
    model = config.get("model", "deepseek-v4-flash")
    base_url = config.get("base_url", "https://api.deepseek.com")
    approval_mode = config.get("approval_mode", "auto")
    provider = config.get("provider", "deepseek")
    enable_planner = str(config.get("enable_planner", True)).lower()
    components = config.get("optional_components", [])

    lines = [
        f"# LikeCodex configuration",
        f"# Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "[llm]",
        f'provider = "{provider}"',
        f'model = "{model}"',
        f'base_url = "{base_url}"',
    ]

    if api_key:
        lines.append(f'api_key = "{api_key}"')

    lines.extend([
        "",
        "[approval]",
        f'mode = "{approval_mode}"',
        "",
        "[agent]",
        f"enable_planner = {enable_planner}",
    ])

    if components:
        lines.extend([
            "",
            "[install]",
        ])
        for comp in components:
            lines.append(f'{comp} = true')

    return "\n".join(lines) + "\n"


def _mask_api_key(content: str, api_key: str) -> str:
    """Replace the actual API key with *** for display."""
    if api_key:
        return content.replace(api_key, "***")
    return content


# ---------------------------------------------------------------------------
# Connectivity test
# ---------------------------------------------------------------------------


async def _test_api_connectivity(
    provider: str,
    api_key: str,
    base_url: str,
) -> bool:
    """Test API connectivity by listing models."""
    if not api_key:
        return False

    try:
        if provider in ("deepseek", "openai"):
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            response = await client.chat.completions.create(
                model=config.get("model", "deepseek-v4-flash"),
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return bool(response.choices)
        else:
            # Generic httpx-based check
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    base_url.rstrip("/") + "/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                return resp.status_code < 500
    except Exception as e:
        console.print(f"[dim]Connection test failed: {e}[/dim]")
        return False


# ---------------------------------------------------------------------------
# Project memory creation
# ---------------------------------------------------------------------------


async def _create_project_memory() -> None:
    """Create a project memory file with scaffold content."""
    memory_dir = Path.cwd() / ".likecodex"
    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_path = memory_dir / "memory.md"

    content = f"""# Project Memory

Created: {datetime.now().strftime('%Y-%m-%d')}

## Project Overview
<!-- Describe what this project does -->

## Conventions
<!-- Coding conventions, patterns, preferences -->

## Architecture
<!-- Key architectural decisions -->
"""
    memory_path.write_text(content, encoding="utf-8")
    console.print(f"[green]✓ Created {memory_path}[/green]")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_setup_wizard())
