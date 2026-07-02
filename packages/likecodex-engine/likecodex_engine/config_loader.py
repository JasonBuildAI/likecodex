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


def _env_or(section: dict[str, Any], key: str, env_key: str, default: Any = "") -> Any:
    """Return env var if set, else config section value, else default.
    Prefers explicit env var over config value.
    """
    if env_key in os.environ:
        return os.environ[env_key]
    if key in section:
        return section[key]
    return default


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
    skills_cfg = merged.get("skills", {})
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
        "provider": _env_or(llm, "provider", "LIKECODEX_LLM_PROVIDER", "deepseek"),
        "model": _env_or(llm, "model", "LIKECODEX_LLM_MODEL", "deepseek-v4-flash"),
        "api_key": api_key,
        "base_url": _env_or(llm, "base_url", "LIKECODEX_LLM_BASE_URL", "https://api.deepseek.com"),
        "deepseek_thinking": str(_env_or(deepseek, "thinking", "LIKECODEX_DEEPSEEK_THINKING", False)).lower(),
        "reasoning_effort": _env_or(deepseek, "reasoning_effort", "LIKECODEX_REASONING_EFFORT"),
        "reasoning_language": _env_or(deepseek, "reasoning_language", "LIKECODEX_REASONING_LANGUAGE"),
        "working_dir": working_dir,
        "approval_mode": _env_or(approval, "mode", "LIKECODEX_APPROVAL_MODE", "auto"),
        "enable_planner": str(_env_or(agent, "enable_planner", "LIKECODEX_ENABLE_PLANNER", False)).lower(),
        "auto_plan": str(_env_or(agent, "auto_plan", "LIKECODEX_AUTO_PLAN", "off")).lower(),
        "auto_plan_classifier": _env_or(agent, "auto_plan_classifier", "LIKECODEX_AUTO_PLAN_CLASSIFIER"),
        "enable_mcp": enable_mcp,
        "mcp_startup": mcp.get("startup", "lazy"),
        "mcp_servers": mcp_servers,
        "token_mode": token_mode,
        "sandbox_executor_url": os.environ.get("LIKECODEX_SANDBOX_URL"),
        "memory_path": os.environ.get("LIKECODEX_MEMORY_PATH", ".likecodex/memory.jsonl"),
        "planner_model": _env_or(agent, "planner_model", "LIKECODEX_PLANNER_MODEL", "deepseek-v4-pro"),
        "compact_ratio": str(_env_or(agent, "compact_ratio", "LIKECODEX_COMPACT_RATIO", 0.8)),
        "soft_compact_ratio": str(_env_or(agent, "soft_compact_ratio", "LIKECODEX_SOFT_COMPACT_RATIO", 0.5)),
        "compact_force_ratio": str(_env_or(agent, "compact_force_ratio", "LIKECODEX_COMPACT_FORCE_RATIO", 0.9)),
        "max_steps": int(agent.get("max_steps", 0)),
        "goal_max_continuations": int(
            os.environ.get("LIKECODEX_GOAL_MAX_CONTINUATIONS")
            or agent.get("goal_max_continuations", 20)
        ),
        "disabled_skills": skills_cfg.get("disabled", []) if isinstance(skills_cfg, dict) else [],
    }
