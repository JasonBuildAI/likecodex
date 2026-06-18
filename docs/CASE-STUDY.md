# LikeCodex Cache Case Study

## Summary

LikeCodex uses a **Cache-First Loop** (ImmutablePrefix + AppendOnlyLog + VolatileScratch) optimized for DeepSeek V4 prefix caching. Benchmark harness: `benchmarks/cache/run.py`.

## Results (mock simulate-cache, 10 turns)

| Metric | Before (flat context) | After (CacheFirst v2) |
|--------|----------------------|------------------------|
| Turn 5+ hit rate | ~40–60% (estimated) | **≥ 94%** |
| Prefix hash stability | unstable | stable per session |
| Compaction | tail trim | ratio-triggered reset |

Run locally:

```bash
uv run python benchmarks/cache/run.py --turns 10 --simulate-cache
cat benchmarks/cache/baseline.json
```

## Differentiators vs Reasonix

1. **Verifiable benchmark** — open script + CI job
2. **Docker sandbox** — risky commands routed to container (`likecodex doctor --security`)
3. **Team API** — Rust HTTP/SSE server + terminal share the same Python loop

## Cost estimate

Based on DeepSeek V4-Flash pricing in `benchmarks/cache/run.py`:

- Cache hit: $0.0028 / 1M tokens
- Cache miss: $0.14 / 1M tokens

Typical 10-turn session savings: **~90%+** vs no-cache baseline (see `savings_pct` in baseline.json).
