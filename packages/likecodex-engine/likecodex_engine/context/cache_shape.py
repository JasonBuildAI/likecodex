"""Prefix-shape snapshots for cache-hit diagnostics (Reasonix parity)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PrefixShape:
    system_hash: str = ""
    tools_hash: str = ""
    prefix_hash: str = ""
    log_rewrite_version: int = 0
    tool_schema_tokens: int = 0


@dataclass
class CacheDiagnostics:
    prefix_hash: str = ""
    prefix_changed: bool = False
    prefix_change_reasons: list[str] = field(default_factory=list)
    system_hash: str = ""
    tools_hash: str = ""
    log_rewrite_version: int = 0
    tool_schema_tokens: int = 0
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _short_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _normalize_tool_schemas(schemas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        schemas,
        key=lambda s: (
            s.get("function", {}).get("name", ""),
            s.get("function", {}).get("description", ""),
            json.dumps(s.get("function", {}).get("parameters", {}), sort_keys=True),
        ),
    )


def _estimate_tokens(text: str) -> int:
    return len(text) // 4 if text else 0


def capture_prefix_shape(
    system_prompt: str,
    tool_schemas: list[dict[str, Any]],
    rewrite_version: int = 0,
) -> PrefixShape:
    normalized = _normalize_tool_schemas(tool_schemas)
    tools_json = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return PrefixShape(
        system_hash=_short_hash(system_prompt),
        tools_hash=_short_hash(tools_json),
        prefix_hash=_short_hash({"system": system_prompt, "tools": tools_json}),
        log_rewrite_version=rewrite_version,
        tool_schema_tokens=_estimate_tokens(tools_json),
    )


def compare_prefix_shape(
    previous: PrefixShape | None,
    current: PrefixShape,
    usage: dict[str, Any] | None,
) -> CacheDiagnostics:
    reasons: list[str] = []
    prev = previous or PrefixShape()
    if prev.system_hash and prev.system_hash != current.system_hash:
        reasons.append("system")
    if prev.tools_hash and prev.tools_hash != current.tools_hash:
        reasons.append("tools")
    if prev.log_rewrite_version != current.log_rewrite_version:
        reasons.append("log_rewrite")

    hit = int((usage or {}).get("prompt_cache_hit_tokens", 0))
    miss = int((usage or {}).get("prompt_cache_miss_tokens", 0))
    return CacheDiagnostics(
        prefix_hash=current.prefix_hash,
        prefix_changed=bool(reasons),
        prefix_change_reasons=reasons,
        system_hash=current.system_hash,
        tools_hash=current.tools_hash,
        log_rewrite_version=current.log_rewrite_version,
        tool_schema_tokens=current.tool_schema_tokens,
        cache_hit_tokens=hit,
        cache_miss_tokens=miss,
    )


def format_usage_line(usage: dict[str, Any] | None, diagnostics: CacheDiagnostics | None) -> str:
    """Render per-turn token/cache summary like Reasonix TextSink."""
    if not usage:
        return ""
    total = int(usage.get("total_tokens", 0))
    if total <= 0:
        return ""

    prompt = int(usage.get("prompt_tokens", 0))
    completion = int(usage.get("completion_tokens", 0))
    hit = int(usage.get("prompt_cache_hit_tokens", 0))
    miss = int(usage.get("prompt_cache_miss_tokens", 0))
    if miss == 0 and prompt > hit:
        miss = prompt - hit

    cache_col = ""
    if prompt > 0:
        cache_col = f" ({hit} cached / {miss} new)"

    reasoning = int(usage.get("reasoning_tokens", 0))
    reasoning_col = f" ({reasoning} reasoning)" if reasoning > 0 else ""

    churn = ""
    if diagnostics and diagnostics.prefix_changed:
        reasons = "+".join(diagnostics.prefix_change_reasons) or "unknown"
        churn = f" · cache prefix changed: {reasons}"

    return f"  · {total} tok · in {prompt}{cache_col} · out {completion}{reasoning_col}{churn}"
