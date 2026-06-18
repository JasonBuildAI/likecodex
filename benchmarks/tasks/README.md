# LikeCodex task benchmarks (lightweight τ-bench subset)

Run scripted agent tasks and record success rate:

```bash
uv run pytest tests/e2e/test_simple_task.py -v
uv run python benchmarks/cache/run.py --turns 10 --simulate-cache
```

## Scenarios

| Task | Description | Target |
|------|-------------|--------|
| bugfix | Fix failing Python test | pass pytest |
| refactor | Rename symbol across files | grep clean |
| testgen | Add unit test for utility | coverage +1 |

See `tests/e2e/` for executable scenarios.
