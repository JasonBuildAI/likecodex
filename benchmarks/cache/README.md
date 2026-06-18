# Cache Benchmark

Measures prefix-cache hit rate for multi-turn LikeCodex sessions.

## Run

```bash
uv run python benchmarks/cache/run.py --turns 10 --simulate-cache
```

Output is written to `benchmarks/cache/baseline.json`.

## KPI

- Turn 1: ~0% hit rate (cold prefix)
- Turn 5+: **≥ 85%** hit rate (mock simulates DeepSeek cache fields)
- `prefix_hash_stable: true` across all turns

## CI

The Python CI job runs this benchmark with `--simulate-cache` (mock provider).
