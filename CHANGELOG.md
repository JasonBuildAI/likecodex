# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Reasonix parity — core coding-agent capabilities** (DeepSeek V4 only):
  - New built-in tools: `ls`, `glob`, `move_file`, `multi_edit`, `delete_range`, `delete_symbol`, `web_fetch` (SSRF-protected), `todo_write`, `notebook_edit`, and background jobs (`bgjobs`)
  - **Non-UTF-8 encoding support**: read/edit/write detect and preserve UTF-8/UTF-16/GBK/GB18030 (CJK Windows round-trip safe)
  - **Shell enhancements**: PowerShell preference on Windows, background job manager with start/list/status/kill
  - **CodeGraph** symbol & reference graph (`codegraph_search`/`codegraph_symbols`/`codegraph_callers`/`codegraph_reindex`) cached to `.likecodex/codegraph.json`, mirrored in the Rust indexer with a `/codegraph/search` endpoint
  - **Diagnostics bridge** (`lsp_diagnostics`) shelling out to ruff/pyright/tsc/go vet/clippy
  - **Checkpoints & rewind**: write-type tools are snapshotted; `/checkpoints` + `/checkpoints/rewind` endpoints and a `likecodex rewind` CLI subcommand
  - **Interactive plan mode**: `complete_step` evidence sign-off (diff/command_output/test_result/file_reference)
  - **Evidence ledger + final-readiness gate**: per-turn tool receipts, todo/project-check gating before final answers
  - **Repeat-success guard** and **stale tool-result pruning** before compaction
  - **Plan exit approval**: `/exit_plan` submits plan; `/exit_plan approve` leaves read-only mode
  - **Sub-agent transcript store** with `continue_from` / `fork_from` on the `task` tool
  - **Executor handoff guard** nudges the executor to use tools after coordinator handoff
  - **Stream recovery** with one retry after `StreamInterruptedError`; partial assistant text preserved; early `tool_dispatch` events during streaming
  - **Subagent stale-running cleanup** marks crash-interrupted refs as `interrupted` on startup
  - **Tool-call pairing sanitize** backfills unanswered calls and pairs empty-ID multi-tool results by position
  - **DeepSeek streaming aggregation** emits `delta`, `tool_dispatch`, and recoverable `StreamInterruptedError`
  - **Full tool_dispatch** events emitted before tool execution; empty tool-call ids assigned before persistence
  - **Web UI** shows assistant streaming placeholder, partial tool cards, and retry notices
  - **Structured stream_retrying events** replace ad-hoc retry stream chunks; Web merges partial/full tool cards by id
  - **Subagent continue** replays transcripts through tool pairing sanitize before LLM send
  - **Compaction SSE events** (`compaction_started` / `compaction_done`) and TUI/Web consumers
  - **Provider stream reconnect** retries connection drops before first output (max 3)
  - **Provider RetryNotify** surfaces transient reconnects as structured `retrying` events (`reason=provider`)
  - **Compaction benchmark** scenario validates `compaction_started`/`compaction_done` in CI
  - **CLI run/chat** handle delta, retrying, tool_dispatch, and compaction events like TUI/Web
  - **Provider HTTP retry on complete()** retries connection drops for compaction/planner calls (max 3)
  - **Empty final answer guard** retries when the model stops with no visible text (max 3), matching Reasonix
  - **Web retry reason labels** show provider vs stream_recovery like TUI/CLI
  - **TUI retry reason labels** distinguish provider reconnect vs stream recovery
  - **Web compaction/retry parsing** tests cover `compaction_started`/`compaction_done` and retry `reason`
  - **StreamRetrying reason field** propagated through Rust SSE to Web UI
  - **Permission streaming parity**: fix `permission_requested` mapping from content JSON; broadcast `permission_responded` on approval; Web clears pending permission cards
  - **Tool result call_id** mapped from stream metadata for SSE consumers
  - **Tool output truncation notices**: head+tail 32KB cap with user-facing `notice` events (Reasonix parity)
  - **finish_reason warnings**: emit notices for `length`, `content_filter`, and `repetition_truncation`
  - **Per-turn usage events** with cache prefix diagnostics (`reason=tools/system/log_rewrite`) matching Reasonix TextSink
  - **Checkpoint SSE events** (`checkpoint_created`) before write-type tools; Web/TUI/CLI consumers show id, label, and files
  - **Executor handoff guard** aligned to Reasonix max 1 nudge before requiring tool use
  - **Slash commands** (`.likecodex/commands/*.md`), **`@path` references**, and **`/init`** generating `LIKECODEX.md` project memory folded into the cache-stable prefix
  - **Cross-turn batch storm breaker** detects repeated all-failing tool batches across turns and nudges the model to change approach (Reasonix `applyStormBreaker`)
  - **Manual `/compact [focus]`** compacts session context on demand with optional summary focus text (Reasonix parity)
  - **TUI/CLI skip partial tool_dispatch** shows one dispatch line per tool call like Reasonix TextSink
  - Dual-model split confirmed: `deepseek-v4-flash` executor + `deepseek-v4-pro` planner on an isolated session
- **DeepSeek V4-only LLM layer** (`deepseek-v4-flash` / `deepseek-v4-pro`) with thinking mode and cache token metrics
- **Prefix-cache optimized context**: static SYSTEM prompt, `[Context]` USER blocks, tail-only compaction
- Session context reuse via `session_id` and in-process `SessionContextCache`
- `/metrics` endpoint (Python engine + Rust proxy) and Web UI cache hit rate display
- Expanded versioned `system.md` prompt (>1024 tokens) for reliable DeepSeek cache hits

### Changed

- Removed Anthropic provider; factory supports `deepseek` and `mock` only
- Default configuration now targets `https://api.deepseek.com`
- Tool schemas sorted deterministically; assistant tool_calls use stable JSON serialization

### Added (prior)

- Rust + Python hybrid agent architecture with CLI, TUI, and Web UI
- Agent loop with tool registry (filesystem, shell, git, code search, review)
- Permission system with approval modes and user prompt flow
- Docker sandbox executor with configurable fallback
- Task planner, sub-agent orchestration, MCP loader, vector memory
- SQLite session persistence and SSE event streaming
- Code indexer HTTP API and comprehensive test suite
- CI workflow for Rust, Python, Web, and Docker

### Security

- Working-directory path confinement for file tools
- Shell/git command hardening via argument-vector execution
- Config redaction and optional API token for `/execute`
- Restricted CORS defaults for local development

## [0.1.0] - 2026-06-19

Initial public release.
