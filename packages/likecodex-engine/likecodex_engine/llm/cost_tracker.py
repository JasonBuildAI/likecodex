"""Token Cost Tracker — per-session token usage tracking and cost calculation.

Tracks token usage per session, calculates costs based on DeepSeek pricing,
persists historic cost data, and provides a cost summary API.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# DeepSeek V4 pricing (per 1M tokens, USD)
PRICING: dict[str, dict[str, float]] = {
    "deepseek-v4-flash": {
        "input": 0.10,
        "output": 0.40,
        "cache_hit": 0.01,
    },
    "deepseek-v4-pro": {
        "input": 0.50,
        "output": 2.00,
        "cache_hit": 0.05,
    },
    "deepseek-v4-pro-thinking": {
        "input": 0.50,
        "output": 2.00,
        "cache_hit": 0.05,
        "reasoning": 0.50,  # additional reasoning token cost
    },
}

DEFAULT_MODEL = "deepseek-v4-flash"


@dataclass
class TokenUsage:
    """Token usage for a single request."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    reasoning_tokens: int = 0
    model: str = DEFAULT_MODEL

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TokenUsage:
        return cls(
            prompt_tokens=int(d.get("prompt_tokens", 0)),
            completion_tokens=int(d.get("completion_tokens", 0)),
            cache_hit_tokens=int(d.get("cache_hit_tokens", d.get("prompt_cache_hit_tokens", 0))),
            cache_miss_tokens=int(d.get("cache_miss_tokens", d.get("prompt_cache_miss_tokens", 0))),
            reasoning_tokens=int(d.get("reasoning_tokens", 0)),
            model=str(d.get("model", DEFAULT_MODEL)),
        )

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def input_cost(self) -> float:
        prices = PRICING.get(self.model, PRICING[DEFAULT_MODEL])
        uncached = self.cache_miss_tokens / 1_000_000 * prices["input"]
        cached = self.cache_hit_tokens / 1_000_000 * prices["cache_hit"]
        return round(uncached + cached, 8)

    @property
    def output_cost(self) -> float:
        prices = PRICING.get(self.model, PRICING[DEFAULT_MODEL])
        base = self.completion_tokens / 1_000_000 * prices["output"]
        reasoning = self.reasoning_tokens / 1_000_000 * prices.get("reasoning", prices["output"])
        return round(base + reasoning, 8)

    @property
    def total_cost(self) -> float:
        return round(self.input_cost + self.output_cost, 8)

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hit_tokens + self.cache_miss_tokens
        if total == 0:
            return 0.0
        return self.cache_hit_tokens / total

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cache_hit_tokens": self.cache_hit_tokens,
            "cache_miss_tokens": self.cache_miss_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "model": self.model,
            "total_tokens": self.total_tokens,
            "input_cost": self.input_cost,
            "output_cost": self.output_cost,
            "total_cost": self.total_cost,
            "cache_hit_rate": round(self.cache_hit_rate, 4),
        }


@dataclass
class SessionCostRecord:
    """Cost record for a single session."""
    session_id: str
    usages: list[TokenUsage] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    model_switch_count: int = 0

    def add_usage(self, usage: TokenUsage) -> None:
        self.usages.append(usage)
        self.updated_at = time.time()

    @property
    def total_input_tokens(self) -> int:
        return sum(u.prompt_tokens for u in self.usages)

    @property
    def total_output_tokens(self) -> int:
        return sum(u.completion_tokens for u in self.usages)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost(self) -> float:
        return round(sum(u.total_cost for u in self.usages), 8)

    @property
    def total_input_cost(self) -> float:
        return round(sum(u.input_cost for u in self.usages), 8)

    @property
    def total_output_cost(self) -> float:
        return round(sum(u.output_cost for u in self.usages), 8)

    @property
    def request_count(self) -> int:
        return len(self.usages)

    @property
    def total_cache_hit_tokens(self) -> int:
        return sum(u.cache_hit_tokens for u in self.usages)

    @property
    def total_cache_miss_tokens(self) -> int:
        return sum(u.cache_miss_tokens for u in self.usages)

    @property
    def overall_cache_hit_rate(self) -> float:
        hit = self.total_cache_hit_tokens
        miss = self.total_cache_miss_tokens
        total = hit + miss
        if total == 0:
            return 0.0
        return hit / total

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "request_count": self.request_count,
            "total_tokens": self.total_tokens,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_input_cost": self.total_input_cost,
            "total_output_cost": self.total_output_cost,
            "total_cost": self.total_cost,
            "total_cache_hit_tokens": self.total_cache_hit_tokens,
            "total_cache_miss_tokens": self.total_cache_miss_tokens,
            "overall_cache_hit_rate": round(self.overall_cache_hit_rate, 4),
            "model_switch_count": self.model_switch_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "duration_seconds": round(time.time() - self.created_at, 2),
        }

    def summary_dict(self) -> dict[str, Any]:
        """Compact summary for API responses."""
        return {
            "session_id": self.session_id,
            "requests": self.request_count,
            "total_cost": self.total_cost,
            "total_tokens": self.total_tokens,
            "cache_hit_rate": round(self.overall_cache_hit_rate, 4),
        }


class CostTracker:
    """Tracks token usage and cost across sessions."""

    def __init__(self, persist_path: str | None = None):
        self._sessions: dict[str, SessionCostRecord] = {}
        self._persist_path = persist_path
        if persist_path:
            self._load()

    def get_or_create_session(self, session_id: str) -> SessionCostRecord:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionCostRecord(session_id=session_id)
        return self._sessions[session_id]

    def record_usage(
        self,
        session_id: str,
        usage: TokenUsage | dict[str, Any],
    ) -> TokenUsage:
        if isinstance(usage, dict):
            usage = TokenUsage.from_dict(usage)
        record = self.get_or_create_session(session_id)
        record.add_usage(usage)
        self._save()
        return usage

    def record_switch_model(self, session_id: str) -> None:
        record = self.get_or_create_session(session_id)
        record.model_switch_count += 1
        self._save()

    def get_session_cost(self, session_id: str) -> SessionCostRecord | None:
        return self._sessions.get(session_id)

    def get_all_sessions(self) -> list[SessionCostRecord]:
        return list(self._sessions.values())

    def get_all_summaries(self) -> list[dict[str, Any]]:
        return [s.summary_dict() for s in self._sessions.values()]

    def get_total_cost(self) -> dict[str, Any]:
        total_cost = sum(s.total_cost for s in self._sessions.values())
        total_tokens = sum(s.total_tokens for s in self._sessions.values())
        total_requests = sum(s.request_count for s in self._sessions.values())
        total_cache_hit = sum(s.total_cache_hit_tokens for s in self._sessions.values())
        total_cache_miss = sum(s.total_cache_miss_tokens for s in self._sessions.values())
        overall_hit = 0.0
        if total_cache_hit + total_cache_miss > 0:
            overall_hit = total_cache_hit / (total_cache_hit + total_cache_miss)
        return {
            "total_sessions": len(self._sessions),
            "total_requests": total_requests,
            "total_cost": round(total_cost, 8),
            "total_tokens": total_tokens,
            "total_cache_hit_tokens": total_cache_hit,
            "total_cache_miss_tokens": total_cache_miss,
            "overall_cache_hit_rate": round(overall_hit, 4),
        }

    def calculate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        cache_hit_tokens: int = 0,
        cache_miss_tokens: int = 0,
        model: str = DEFAULT_MODEL,
    ) -> dict[str, float]:
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_hit_tokens=cache_hit_tokens,
            cache_miss_tokens=cache_miss_tokens,
            model=model,
        )
        return {
            "input_cost": usage.input_cost,
            "output_cost": usage.output_cost,
            "total_cost": usage.total_cost,
            "model": model,
            "cache_hit_rate": round(usage.cache_hit_rate, 4),
        }

    def clear_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._save()
            return True
        return False

    def reset_all(self) -> None:
        self._sessions.clear()
        if self._persist_path:
            path = Path(self._persist_path)
            if path.exists():
                path.unlink()

    def _persist_path_resolved(self) -> Path:
        if not self._persist_path:
            return Path("cost_tracker_data.json")
        return Path(self._persist_path)

    def _load(self) -> None:
        try:
            path = self._persist_path_resolved()
            if not path.exists():
                return
            data = json.loads(path.read_text(encoding="utf-8"))
            for sid, record_data in data.get("sessions", {}).items():
                record = SessionCostRecord(
                    session_id=sid,
                    usages=[TokenUsage.from_dict(u) for u in record_data.get("usages", [])],
                    created_at=record_data.get("created_at", time.time()),
                    updated_at=record_data.get("updated_at", time.time()),
                    model_switch_count=record_data.get("model_switch_count", 0),
                )
                self._sessions[sid] = record
        except Exception as e:
            logger.warning("Failed to load cost tracker data: %s", e)

    def _save(self) -> None:
        if not self._persist_path:
            return
        try:
            path = self._persist_path_resolved()
            data = {
                "sessions": {
                    sid: {
                        "usages": [asdict(u) for u in record.usages],
                        "created_at": record.created_at,
                        "updated_at": record.updated_at,
                        "model_switch_count": record.model_switch_count,
                    }
                    for sid, record in self._sessions.items()
                }
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to persist cost tracker data: %s", e)


# Global singleton
_global_tracker: CostTracker | None = None


def get_cost_tracker(persist_path: str | None = None) -> CostTracker:
    """Get or create the global CostTracker instance."""
    global _global_tracker
    if _global_tracker is None:
        # Default persist path in user data dir or cwd
        default_path = os.environ.get(
            "LIKECODEX_COST_DATA",
            str(Path.cwd() / ".likecodex" / "cost_tracker.json"),
        )
        _global_tracker = CostTracker(persist_path=persist_path or default_path)
    return _global_tracker


def reset_cost_tracker() -> None:
    """Reset the global cost tracker."""
    global _global_tracker
    _global_tracker = None
