# LikeCodex E2E task benchmarks (Reasonix parity subset)

Ported scenarios from Reasonix `benchmarks/e2e/tasks/`:

| Task | Description | Verify |
|------|-------------|--------|
| fix-add-bug | Fix off-by-one in `add()` | `verify.sh` runs pytest-style assert |
| fizzbuzz | Implement classic FizzBuzz | output assert |
| palindrome | Fix palindrome checker | assert |
| compaction | Agent triggers context compaction | archive file exists |
| subagent-delegation | Delegates via task/subagent | subagent artifact exists |

Run a single task after agent completes in `workspace/`:

```bash
bash benchmarks/tasks/fix-add-bug/verify.sh
```

Agent harness mock regression remains in `benchmarks/agent/run.py` (CI `agent-parity` job).
