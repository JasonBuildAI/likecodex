"""Aggregate DeepSeek context-cache hit statistics."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CacheMetrics:
    """Rolling cache hit/miss counters."""

    total_hit_tokens: int = 0
    total_miss_tokens: int = 0
    request_count: int = 0
    cache_reset_count: int = 0
    recent_hit_rates: list[float] = field(default_factory=list)
    max_recent: int = 100

    def reset(self) -> None:
        self.total_hit_tokens = 0
        self.total_miss_tokens = 0
        self.request_count = 0
        self.cache_reset_count = 0
        self.recent_hit_rates.clear()

    def record(self, usage: dict[str, int] | None) -> None:
        if not usage:
            return
        hit = int(usage.get("prompt_cache_hit_tokens", 0))
        miss = int(usage.get("prompt_cache_miss_tokens", 0))
        self.total_hit_tokens += hit
        self.total_miss_tokens += miss
        self.request_count += 1
        total = hit + miss
        if total > 0:
            self.recent_hit_rates.append(hit / total)
            if len(self.recent_hit_rates) > self.max_recent:
                self.recent_hit_rates.pop(0)

    @property
    def hit_rate(self) -> float:
        total = self.total_hit_tokens + self.total_miss_tokens
        if total == 0:
            return 0.0
        return self.total_hit_tokens / total

    @property
    def recent_hit_rate(self) -> float:
        if not self.recent_hit_rates:
            return 0.0
        return sum(self.recent_hit_rates) / len(self.recent_hit_rates)

    def to_dict(self) -> dict[str, float | int]:
        return {
            "request_count": self.request_count,
            "total_hit_tokens": self.total_hit_tokens,
            "total_miss_tokens": self.total_miss_tokens,
            "hit_rate": round(self.hit_rate, 4),
            "recent_hit_rate": round(self.recent_hit_rate, 4),
        }


_GLOBAL_METRICS = CacheMetrics()


def global_cache_metrics() -> CacheMetrics:
    return _GLOBAL_METRICS


def reset_global_cache_metrics() -> None:
    _GLOBAL_METRICS.reset()
