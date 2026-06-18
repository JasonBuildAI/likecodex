# LikeCodex Architecture

LikeCodex is a Rust + Python hybrid coding agent powered by **DeepSeek V4**, optimized for context cache hit rate.

## Layers

```text
Interface        CLI (Rust)          Web UI (Next.js + Rust Axum backend)
                     |                            |
                     +-------------+--------------+
                                   |
                         HTTP / SSE bridge
                                   |
Control          Python Agent Engine (agent loop, planner, permissions)
                                   |
Tools            Python tools (filesystem, shell, git, code search, review, MCP)
                                   |
Execution        Rust executors (local, Docker sandbox)
                                   |
Models           DeepSeek V4 (Flash/Pro) via OpenAI-compatible API
                                   |
Persistence      SQLite sessions, JSONL events, vector memory
```

## Key Components

- `crates/likecodex-core`: shared types, configuration, event bus.
- `crates/likecodex-cli`: terminal interface and TUI.
- `crates/likecodex-server`: Axum web server that bridges to the Python engine.
- `crates/likecodex-executor`: local command execution.
- `crates/likecodex-sandbox`: Docker sandbox orchestration with local fallback.
- `crates/likecodex-indexer`: file indexing placeholder for large codebases.
- `packages/likecodex-engine`: Python agent core (loop, LLM, tools, context, memory).
- `web/`: Next.js frontend consuming the Rust server SSE events.

## Communication

- Rust CLI/Web talks to Python engine over HTTP (`/run`, `/chat`, `/tasks`, `/plan`).
- Streaming responses use Server-Sent Events (SSE).
- All agent outputs are normalized as events so CLI and Web share the same experience.

## Cache Architecture

DeepSeek context caching requires a **byte-stable prefix** from token 0:

1. Single frozen `system.md` SYSTEM message (version `PROMPT_VERSION=1`)
2. Sorted tool schemas passed as API `tools` parameter
3. Conversation history appended after the prefix
4. Dynamic memory/sub-agent data as trailing `[Context]` USER messages
5. Session reuse preserves prefix across HTTP requests with the same `session_id`

Metrics: `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` aggregated at `GET /metrics`.

## Security

- Approval modes: `read-only`, `auto`, `full-access`, `sandbox-required`.
- High-risk shell commands can be routed to a Docker sandbox.
- Sandbox falls back to local execution when Docker is unavailable.
