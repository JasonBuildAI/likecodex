# LikeCodex Architecture

LikeCodex is a Rust + Python hybrid coding agent inspired by OpenAI Codex.

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
Models           Python LLM clients (OpenAI, Anthropic, mock)
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

## Security

- Approval modes: `read-only`, `auto`, `full-access`, `sandbox-required`.
- High-risk shell commands can be routed to a Docker sandbox.
- Sandbox falls back to local execution when Docker is unavailable.
