# Reasonix Core Parity Checklist

Maps in-scope Reasonix capabilities to LikeCodex implementation and tests.

| # | Capability | LikeCodex | Test |
|---|------------|-----------|------|
| 1 | Loop/storm guard | `agent/guards.py` | `tests/test_agent_guards.py` |
| 2 | Plan mode tool/bash filter | `agent/plan_mode.py` | `tests/test_plan_mode.py` |
| 3 | Read-only parallel dispatch | `agent/dispatch.py` | `tests/test_agent_loop.py` |
| 4 | Tool output 32KB cap + truncation notice | `agent/output_limit.py` | `tests/test_output_notices.py`, `tests/test_harness_integration.py` |
| 5 | Coordinator dual-model | `agent/coordinator.py` | `tests/test_coordinator.py`, `tests/test_planner.py` |
| 6 | VolatileScratch wiring | `context/cache_first.py` | `tests/test_cache_first.py` |
| 7 | LLM compaction + archive | `context/compaction.py` | `tests/test_compact_loop.py` |
| 8 | history tool (BM25) | `tools/history.py` | `tests/test_history_tool.py` |
| 9 | remember/forget/search | `tools/agent_memory.py` | `tests/test_agent_memory.py` |
| 10 | task sub-agent | `agent/task.py` + `agent/subagent_store.py` | `tests/test_task_tool.py`, `tests/test_subagent_store.py` |
| 11 | parallel_tasks | `agent/parallel_tasks.py` | `tests/test_parallel_tasks.py` |
| 12 | run_skill inline/subagent | `skills/runner.py` | `tests/test_run_skill.py` |
| 13 | Meta tool isolation | `agent/subagent_registry.py` | `tests/test_subagent.py` |
| 14 | LSP definition/refs/hover/diag | `lsp/` + `tools/lsp_tools.py` | `tests/test_lsp_tools.py` |
| 15 | code_index fallback | `tools/code_index.py` | `tests/test_codegraph.py` |
| 16 | Plan state machine | `agent/plan_state.py` | `tests/test_plan_state.py` |
| 17 | complete_step verification | `tools/plan_progress.py` + `agent/evidence.py` | `tests/test_complete_step.py`, `tests/test_evidence.py` |
| 18 | todo + complete_step linkage | `tools/todo.py` | `tests/test_complete_step.py`, `tests/test_harness_integration.py` |
| 19 | Policy rules allow/ask/deny | `permissions/policy.py` | `tests/test_permissions.py` |
| 20 | read_file offset/limit + line nums | `tools/filesystem.py` | `tests/test_read_file_window.py` |
| 21 | gitignore-aware grep | `tools/code_search.py` | `tests/test_grep_gitignore.py` |
| 22 | bash_output/kill_shell/wait | `tools/shell.py` | `tests/test_shell_jobs.py` |
| 23 | Encoding round-trip | `tools/encoding.py` | `tests/test_encoding.py` |
| 26 | Evidence ledger (per-turn receipts) | `agent/evidence.py` | `tests/test_evidence.py` |
| 27 | Final-readiness gate | `agent/readiness.py` | `tests/test_readiness.py`, `tests/test_harness_integration.py` |
| 28 | Repeat-success guard | `agent/guards.py` | `tests/test_repeat_guard.py` |
| 29 | Prune stale tool results | `context/prune.py` | `tests/test_prune.py` |
| 30 | Stream recovery (max 1 retry) | `agent/streaming.py` + `llm/errors.py` | `tests/test_stream_recovery.py` |
| 31 | Early tool_dispatch during stream | `agent/streaming.py` | `tests/test_stream_recovery.py` |
| 32 | Subagent stale-running cleanup | `agent/subagent_store.py` | `tests/test_subagent_store.py` |
| 33 | Loop e2e (tool round-trip, parallel reads) | `agent/loop.py` | `tests/test_loop_e2e.py` |
| 34 | Tool-call pairing sanitize before API send | `llm/tool_repair.py` | `tests/test_tool_repair.py`, `tests/test_loop_e2e.py` |
| 35 | OpenAI-compatible stream aggregation | `llm/openai_stream.py` + `llm/deepseek.py` | `tests/test_openai_stream.py` |
| 36 | SSE delta/tool_dispatch/retrying mapping | `crates/likecodex-server/src/event_mapping.rs` | Rust unit tests |
| 37 | Full tool_dispatch before execution | `agent/loop.py` | `tests/test_dispatch.py` |
| 38 | Empty tool-call id assignment | `llm/tool_repair.py` | `tests/test_dispatch.py`, `tests/test_loop_e2e.py` |
| 39 | Web UI streaming UX (retry/dispatch) | `web/src/lib/api.ts` | `web/src/lib/api.test.ts` |
| 40 | Structured `stream_retrying` event | `crates/likecodex-core/src/events.rs` | Rust + web tests |
| 41 | Subagent continue sanitize replay | `context/cache_first.py` | `tests/test_subagent_sanitize.py` |
| 42 | Web tool dispatch merge by id | `web/src/lib/store.ts` | `web/src/lib/api.test.ts` |
| 43 | Compaction started/done SSE events | `agent/loop.py` + `events.rs` | `tests/test_compaction_events.py` |
| 44 | TUI delta/retry/dispatch/compaction | `crates/likecodex-cli/src/tui.rs` | manual |
| 45 | Provider pre-output stream reconnect | `llm/openai_stream.py` | `tests/test_openai_stream.py` |
| 46 | Provider RetryNotify → retrying events | `llm/retry.py` | `tests/test_provider_retry.py` |
| 47 | Compaction benchmark scenario | `benchmarks/agent/run.py` | CI `--check` |
| 48 | CLI stream event parity (run/chat) | `crates/likecodex-cli/src/main.rs` | manual |
| 49 | Provider HTTP retry on complete() | `llm/openai_stream.py` | `tests/test_openai_stream.py`, `tests/test_provider_retry.py` |
| 50 | Empty final answer guard (max 3) | `agent/guards.py` + `agent/loop.py` | `tests/test_empty_final.py` |
| 51 | Web retry reason + compaction parse | `web/src/lib/api.ts` | `web/src/lib/api.test.ts` |
| 52 | TUI/CLI retry reason labels | `tui.rs` + `main.rs` | manual |
| 53 | Permission requested SSE (content JSON) | `event_mapping.rs` | Rust unit tests |
| 54 | Permission responded SSE broadcast | `main.rs` + `events.rs` | `web/src/lib/api.test.ts` |
| 55 | Permission prompt/respond loop | `agent/loop.py` | `tests/test_permission_events.py` |
| 56 | Tool result call_id from metadata | `event_mapping.rs` | Rust unit tests |
| 57 | Tool output truncation notice (head+tail) | `agent/output_limit.py` + `loop.py` | `tests/test_output_notices.py` |
| 58 | finish_reason warning notices | `agent/guards.py` + `loop.py` | `tests/test_output_notices.py` |
| 59 | Per-turn usage + cache diagnostics | `context/cache_shape.py` + `loop.py` | `tests/test_cache_diagnostics.py` |
| 60 | Checkpoint SSE before write tools | `loop.py` + `events.rs` | `tests/test_checkpoint_events.py` |
| 61 | Executor handoff guard (max 1 nudge) | `agent/guards.py` + `loop.py` | `tests/test_handoff_guard.py` |
| 62 | Slash commands + @ references + /init | `agent/commands.py` + `server.py` | `tests/test_commands.py` |
| 63 | Checkpoint rewind API + CLI | `checkpoints.py` + `main.rs` | `tests/test_checkpoints.py` |
| 64 | Cross-turn batch storm breaker | `agent/guards.py` + `agent/loop.py` | `tests/test_storm_breaker.py` |
| 65 | Manual `/compact [focus]` command | `agent/commands.py` + `server.py` | `tests/test_commands.py`, `tests/test_compact_loop.py` |
| 66 | TUI/CLI skip partial tool_dispatch | `tui.rs` + `main.rs` | manual |
| 24 | Agent task benchmark | `benchmarks/agent/` | CI job |
| 25 | Cache benchmark | `benchmarks/cache/run.py` | CI job |

**DoD:** All rows implemented with passing tests; agent benchmark within ±20% steps vs mock baseline.
