# LikeCodex Cache-First Specification

This document is the contract for DeepSeek prefix-cache behavior in LikeCodex.
Code follows this spec; change the spec first, then the code.

## 1. Design Principles

1. **Cache stability is an invariant**, not an optional optimization.
2. **DeepSeek-only**: one provider, one base URL, predictable prefix bytes.
3. **Static prefix first, dynamic suffix last**: from token 0, bytes must match across turns.
4. **Planner and sub-agents use separate sessions**; never append their turns to the executor prefix.
5. **Tool payloads are byte-stable**: deterministic JSON, raw replay, no re-serialization.

## 2. Three-Region Context Model

```text
┌─────────────────────────────────────────┐
│ IMMUTABLE PREFIX                        │  fixed per session (+ skills pin)
│   system.md + skills block + tool specs │
├─────────────────────────────────────────┤
│ APPEND-ONLY LOG                         │  monotonic assistant/tool/user turns
│   [assistant][tool][user]...            │
├─────────────────────────────────────────┤
│ VOLATILE SCRATCH                        │  never sent upstream
│   thinking traces, planner raw output   │
└─────────────────────────────────────────┘
```

### 2.1 ImmutablePrefix

- Loaded once from [`prompts/system.md`](../packages/likecodex-engine/likecodex_engine/prompts/system.md) (`PROMPT_VERSION=N`).
- Optional sorted **skills block** appended inside the single SYSTEM message.
- `prefix_hash = sha256(system + skills)` computed at session start.
- Must not contain: timestamps, session IDs, working directory paths, random IDs.

### 2.2 AppendOnlyLog

- Stores `assistant`, `tool`, and non-scratch `user` messages in order.
- Each assistant message stores `raw_tool_calls` (deterministic JSON string).
- Each tool message stores exact result string returned to the model.
- **No rewrites** except at explicit compaction (cache-reset point).

### 2.3 VolatileScratch

- Holds planner reasoning, sub-agent raw dumps, R1 `reasoning_content` if harvested locally.
- **Excluded** from `build_for_llm()`.
- Distilled summaries enter the log as `[Context]` USER messages only.

## 3. Dynamic Context Rules

| Content type | Role | Prefix position |
|--------------|------|-----------------|
| User task prompt | USER | end of log |
| Memory / sub-agent summary | USER with `[Context]\n` | before latest user, after log history |
| Plan for executor | USER with `[Plan]\n` | before latest user |
| System policy change | forbidden mid-session | — |

## 4. Compaction (Cache-Reset)

Compaction is **low-frequency** and intentional:

- Trigger when `prompt_tokens >= compact_ratio * context_window` (default `0.8`).
- Default `context_window` for DeepSeek V4: `1_000_000`.
- On compact:
  1. Generate one USER summary message (rule-based or cheap model).
  2. Clear append-only log except summary.
  3. Preserve ImmutablePrefix unchanged.
  4. Emit `cache_reset` metric event.

Between compactions, the session grows prepend-only and stays cache-friendly.

## 5. Session Model

- **One default session per working directory**: `session_id = sha256(canonical_working_dir)[:16]`.
- CLI/TUI attach automatically; HTTP clients may pass `session_id` explicitly.
- MCP tools are snapshotted at session start; registry order must be stable (sorted by name).

## 6. Planner / Sub-Agent Isolation

- Planner runs in **separate session** with its own context (never executor log).
- Planner output is injected to executor as `[Plan]\n...` USER message only.
- Sub-agents with `runAs: subagent` spawn isolated sessions; executor receives distilled `[Context]` block.

## 7. Tool Schema and Repair

- Tool schemas sorted by name; `json.dumps(..., sort_keys=True)`.
- Nested schemas flattened before API call (see `tool_repair.flatten_schema`).
- Broken tool JSON repaired before execution; leaked calls scavenged from reasoning text.

## 8. Metrics

Every completion records:

- `prompt_cache_hit_tokens`
- `prompt_cache_miss_tokens`
- `hit_rate = hit / (hit + miss)`

Exposed at `GET /metrics` and CLI `likecodex stats`.

## 9. Benchmark Acceptance

[`benchmarks/cache/run.py`](../benchmarks/cache/run.py) must report:

- Turn 1 hit_rate (expect ~0%)
- Turn 5+ hit_rate (target **≥ 85%** with mock simulate_cache or real API)
- `prefix_hash` stable across turns

## 10. Non-Goals

- Multi-provider LLM support (breaks prefix pinning).
- Mid-session SYSTEM message injection.
- Rewriting historical assistant/tool messages for formatting.
