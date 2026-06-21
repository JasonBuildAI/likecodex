"""Configuration loading with project-level merge."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


def _merge_dict(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def _parse_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def project_config_paths(cwd: Path) -> list[Path]:
    stack: list[Path] = []
    current = cwd.resolve()
    while True:
        for name in (".likecodex/config.toml", "likecodex.toml"):
            candidate = current / name
            if candidate.exists():
                stack.append(candidate)
        if current.parent == current:
            break
        current = current.parent
    stack.reverse()
    return stack


def load_merged_config(cwd: Path | None = None) -> dict[str, Any]:
    """Merge user + project configs into a flat engine config dict."""
    cwd = cwd or Path.cwd()
    merged: dict[str, Any] = {}

    user_path = Path.home() / ".likecodex" / "config.toml"
    if user_path.exists():
        merged = _merge_dict(merged, _parse_toml(user_path))

    for path in project_config_paths(cwd):
        merged = _merge_dict(merged, _parse_toml(path))

    return merged


def engine_config_from_env(cwd: Path | None = None) -> dict[str, Any]:
    """Build engine runtime config from merged TOML + environment."""
    merged = load_merged_config(cwd)
    llm = merged.get("llm", {})
    approval = merged.get("approval", {})
    agent = merged.get("agent", {})
    deepseek = merged.get("deepseek", {})
    mcp = merged.get("mcp", {})

    api_key = (
        os.environ.get("LIKECODEX_LLM_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or llm.get("api_key")
    )

    mcp_servers = mcp.get("servers", {})
    if isinstance(mcp_servers, dict):
        mcp_servers = {
            name: cfg for name, cfg in mcp_servers.items() if isinstance(cfg, dict)
        }
    else:
        mcp_servers = {}

    enable_mcp = os.environ.get("LIKECODEX_ENABLE_MCP")
    if enable_mcp is None:
        enable_mcp = str(mcp.get("enabled", False)).lower() in ("1", "true", "yes")
    else:
        enable_mcp = enable_mcp.lower() in ("1", "true", "yes")

    token_mode = os.environ.get("LIKECODEX_TOKEN_MODE") or agent.get("token_mode", "full")

    working_dir = os.environ.get("LIKECODEX_WORKING_DIR", str(cwd or Path.cwd()))

    return {
        "provider": os.environ.get("LIKECODEX_LLM_PROVIDER") or llm.get("provider", "deepseek"),
        "model": os.environ.get("LIKECODEX_LLM_MODEL") or llm.get("model", "deepseek-v4-flash"),
        "api_key": api_key,
        "base_url": os.environ.get("LIKECODEX_LLM_BASE_URL")
        or llm.get("base_url", "https://api.deepseek.com"),
        "deepseek_thinking": os.environ.get("LIKECODEX_DEEPSEEK_THINKING")
        or str(deepseek.get("thinking", False)).lower(),
        "working_dir": working_dir,
        "approval_mode": os.environ.get("LIKECODEX_APPROVAL_MODE") or approval.get("mode", "auto"),
        "enable_planner": os.environ.get("LIKECODEX_ENABLE_PLANNER")
        or str(agent.get("enable_planner", False)).lower(),
        "enable_mcp": enable_mcp,
        "mcp_startup": mcp.get("startup", "lazy"),
        "mcp_servers": mcp_servers,
        "token_mode": token_mode,
        "sandbox_executor_url": os.environ.get("LIKECODEX_SANDBOX_URL"),
        "memory_path": os.environ.get("LIKECODEX_MEMORY_PATH", ".likecodex/memory.jsonl"),
        "planner_model": os.environ.get("LIKECODEX_PLANNER_MODEL")
        or agent.get("planner_model", "deepseek-v4-pro"),
        "compact_ratio": os.environ.get("LIKECODEX_COMPACT_RATIO")
        or str(agent.get("compact_ratio", 0.8)),
    }
