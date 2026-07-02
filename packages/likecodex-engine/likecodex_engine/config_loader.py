"""Configuration loading with project-level merge.

Provides unified configuration loading from:
1. Environment variables (LIKECODEX_* namespace)
2. User config (~/.likecodex/config.toml)
3. Project config (.likecodex/config.toml, likecodex.toml, likecodex.config.toml)

Supports config validation, caching, and hot-reload.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

__all__ = [
    "load_merged_config",
    "engine_config_from_env",
    "project_config_paths",
    "validate_config",
    "clear_config_cache",
    "ConfigValidationError",
    "get_config_with_hot_reload",
]

# ── Config cache: cleared when the module is reloaded ──────────
_CONFIG_CACHE: dict[str, dict[str, Any]] = {}
_LAST_ENV_SNAPSHOT: dict[str, str | None] = {}
_LAST_CACHE_CLEAR: float = 0.0


class ConfigValidationError(Exception):
    """Raised when the configuration fails validation."""

    def __init__(self, missing_fields: list[str]) -> None:
        self.missing_fields = missing_fields
        super().__init__(f"Missing required config fields: {', '.join(missing_fields)}")


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
    """Find all project-level config files walking up from cwd.

    Searches for:
    - .likecodex/config.toml
    - likecodex.toml
    - likecodex.config.toml
    """
    stack: list[Path] = []
    current = cwd.resolve()
    while True:
        for name in (".likecodex/config.toml", "likecodex.toml", "likecodex.config.toml"):
            candidate = current / name
            if candidate.exists():
                stack.append(candidate)
        if current.parent == current:
            break
        current = current.parent
    stack.reverse()
    return stack


def validate_config(config: dict[str, Any]) -> None:
    """Validate that required config fields are present.

    Required fields: api_key, model
    Raises ConfigValidationError if any required fields are missing.
    """
    missing: list[str] = []
    if not config.get("api_key"):
        missing.append("api_key")
    if not config.get("model"):
        missing.append("model")
    if missing:
        raise ConfigValidationError(missing)


def clear_config_cache() -> None:
    """Clear the configuration cache, forcing a reload on next access."""
    global _CONFIG_CACHE, _LAST_CACHE_CLEAR
    _CONFIG_CACHE.clear()
    _LAST_CACHE_CLEAR = time.time()


def _take_env_snapshot() -> dict[str, str | None]:
    """Take a snapshot of all LIKECODEX_* environment variables."""
    snapshot: dict[str, str | None] = {}
    for key, value in os.environ.items():
        if key.startswith("LIKECODEX_") or key in ("DEEPSEEK_API_KEY",):
            snapshot[key] = value
    return snapshot


def _env_has_changed() -> bool:
    """Check if relevant environment variables have changed since last load."""
    global _LAST_ENV_SNAPSHOT
    current = _take_env_snapshot()
    changed = current != _LAST_ENV_SNAPSHOT
    _LAST_ENV_SNAPSHOT = current
    return changed


def _setup_signal_handler() -> None:
    """Set up SIGUSR1 handler to clear config cache (for hot-reload).

    On Windows, SIGUSR1 is not available, so this is best-effort.
    """
    if sys.platform != "win32":
        try:

            def _handler(signum: int, frame: Any) -> None:
                clear_config_cache()

            signal.signal(signal.SIGUSR1, _handler)  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


# Call once at module load time
_setup_signal_handler()


def load_merged_config(cwd: Path | None = None, *, validate: bool = False) -> dict[str, Any]:
    """Merge user + project configs into a flat engine config dict.

    Result is cached per working directory to avoid repeated file I/O.
    The cache is automatically cleared when environment variables change.

    Args:
        cwd: Working directory to search for project configs.
        validate: If True, validate required fields after loading.

    Returns:
        Merged configuration dictionary.

    Raises:
        ConfigValidationError: If validate=True and required fields are missing.
    """
    cwd = cwd or Path.cwd()
    key = str(cwd.resolve())

    # Auto-detect env changes and invalidate cache
    if _env_has_changed():
        clear_config_cache()

    if key in _CONFIG_CACHE:
        return dict(_CONFIG_CACHE[key])  # Return a shallow copy for safety

    merged: dict[str, Any] = {}

    user_path = Path.home() / ".likecodex" / "config.toml"
    if user_path.exists():
        merged = _merge_dict(merged, _parse_toml(user_path))

    for path in project_config_paths(cwd):
        merged = _merge_dict(merged, _parse_toml(path))

    _CONFIG_CACHE[key] = dict(merged)
    result = dict(_CONFIG_CACHE[key])

    if validate:
        validate_config(result)

    return result


def engine_config_from_env(cwd: Path | None = None, *, validate: bool = False) -> dict[str, Any]:
    """Build engine runtime config from merged TOML + environment.

    All LIKECODEX_* environment variables take precedence over config file values.

    Args:
        cwd: Working directory to search for project configs.
        validate: If True, validate required fields after loading.

    Returns:
        Engine runtime configuration dictionary.
    """
    merged = load_merged_config(cwd, validate=validate)
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

    result: dict[str, Any] = {
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
        # Environment-level overrides for all LIKECODEX_* vars
        "engine_host": os.environ.get("LIKECODEX_ENGINE_HOST", "127.0.0.1"),
        "engine_port": int(os.environ.get("LIKECODEX_ENGINE_PORT", "9090")),
        "session_db": os.environ.get("LIKECODEX_SESSION_DB", ".likecodex/sessions.db"),
        "sandbox_url": os.environ.get("LIKECODEX_SANDBOX_URL"),
        "home": os.environ.get("LIKECODEX_HOME"),
        "engine_root": os.environ.get("LIKECODEX_ENGINE_ROOT"),
    }

    return result


def get_config_with_hot_reload(cwd: Path | None = None, *, validate: bool = False) -> dict[str, Any]:
    """Get config with automatic hot-reload detection.

    Checks if environment or files have changed and reloads if necessary.
    This is a convenience wrapper around engine_config_from_env.

    Args:
        cwd: Working directory to search for project configs.
        validate: If True, validate required fields after loading.

    Returns:
        Engine runtime configuration dictionary.
    """
    return engine_config_from_env(cwd, validate=validate)
