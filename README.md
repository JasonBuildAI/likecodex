# LikeCodex

[![CI](https://github.com/JasonBuildAI/likecodex/actions/workflows/ci.yml/badge.svg)](https://github.com/JasonBuildAI/likecodex/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Rust](https://img.shields.io/badge/rust-1.70+-orange.svg)](https://www.rust-lang.org/)
[![Node.js 20+](https://img.shields.io/badge/node.js-20+-green.svg)](https://nodejs.org/)

**LikeCodex** is an open-source coding agent powered by **DeepSeek V4**. It combines a **Rust control plane** (CLI, HTTP API, sandbox execution) with a **Python agent engine** (LLM loop, tools, planning, memory) and a **Next.js web UI** — optimized for **DeepSeek context cache hit rate** to reduce API cost on multi-turn tool loops.

**[中文文档 README.zh-CN.md](README.zh-CN.md)**

---

## Table of Contents

- [What Is LikeCodex?](#what-is-likecodex)
- [Architecture](#architecture)
  - [Design Philosophy](#design-philosophy)
  - [Four-Layer Model](#four-layer-model)
  - [Runtime Topology](#runtime-topology)
  - [Component Map](#component-map)
  - [End-to-End Request Flow](#end-to-end-request-flow)
  - [Agent Loop (Python Engine)](#agent-loop-python-engine)
  - [Event Protocol (SSE)](#event-protocol-sse)
  - [Cache-First Context Model](#cache-first-context-model)
  - [Security and Execution Routing](#security-and-execution-routing)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Built-in Tools](#built-in-tools)
- [Configuration](#configuration)
- [Development](#development)
- [Testing](#testing)
- [Project Layout](#project-layout)
- [Documentation](#documentation)
- [Roadmap](#roadmap)
- [Contributing & License](#contributing--license)

---

## What Is LikeCodex?

LikeCodex helps you **edit, run, and understand code** through natural language. You describe a task; the agent reads files, runs commands, writes patches, and reports back — with optional human approval for risky operations.

Most coding agents are either:

- a **thin CLI wrapper** around an LLM API, or
- a **monolithic Python app** where UI, security, and agent logic are tangled together.

LikeCodex deliberately **splits responsibilities**:

| Concern | Where it lives | Why |
|---------|----------------|-----|
| Fast, safe shell/git execution | Rust | Path confinement, sandbox routing, low overhead |
| Agent logic iteration | Python | Tool loop, LLM providers, planning, compaction |
| Unified UX for CLI + Web | Rust server + SSE events | One event schema for all clients |
| Rich browser UI | Next.js | Chat, diffs, permissions, session history |

**Default LLM:** DeepSeek V4 (`deepseek-v4-flash` or `deepseek-v4-pro`) via OpenAI-compatible API.

---

## Architecture

### Design Philosophy

1. **Separation of control and intelligence** — Rust handles I/O, HTTP, permissions broadcast, and command execution; Python handles reasoning and tool orchestration.
2. **One event stream for all clients** — CLI, TUI, and Web subscribe to the same normalized SSE events from `likecodex-server`.
3. **Cache stability as a first-class invariant** — context is structured so DeepSeek prefix caching stays hot across tool-loop turns (see [Cache-First Context Model](#cache-first-context-model)).
4. **Defense in depth** — path confinement, risk-based command routing, user approval, and optional Docker sandbox.

---

### Four-Layer Model

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 1 — INTERFACES (how you talk to LikeCodex)                        │
│   • likecodex-cli     one-shot / REPL / Ratatui TUI                     │
│   • web/              Next.js three-column UI (:3000)                    │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │  HTTP + SSE
┌───────────────────────────────▼─────────────────────────────────────────┐
│ LAYER 2 — CONTROL PLANE (likecodex-server, :8080)                       │
│   • Forward /tasks, /chat, /run, /plan to Python engine                 │
│   • Broadcast normalized events on GET /events                          │
│   • Permission API + session persistence proxy                          │
│   • POST /execute → Docker sandbox or local executor                    │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │  HTTP (engine bridge)
┌───────────────────────────────▼─────────────────────────────────────────┐
│ LAYER 3 — AGENT ENGINE (likecodex-engine, :9090)                        │
│   • AgentLoop — multi-turn LLM ↔ tool cycle                             │
│   • ToolRegistry — filesystem, shell, git, search, MCP, …              │
│   • ContextManager — cache-first prompt assembly + compaction            │
│   • Permissions — policy + approval modes                               │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │  tool calls
┌───────────────────────────────▼─────────────────────────────────────────┐
│ LAYER 4 — EXECUTION (Rust)                                              │
│   • likecodex-executor   local shell/git with working-dir limits        │
│   • likecodex-sandbox    Docker-isolated commands                       │
│   • likecodex-indexer    filename / code graph search helpers           │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    DeepSeek V4 API (OpenAI-compatible)
```

---

### Runtime Topology

When you run `scripts/dev.sh` or `scripts/dev.ps1`, three processes start:

| Process | Port | Package | Role |
|---------|------|---------|------|
| Python engine | **9090** | `likecodex-engine` | Agent brain — loop, tools, LLM |
| Rust API server | **8080** | `likecodex-server` | Bridge, SSE bus, sandbox gateway |
| Next.js dev server | **3000** | `web/` | Browser UI (proxies API in dev) |

**Health checks:**

```bash
curl http://127.0.0.1:9090/health   # Python engine
curl http://127.0.0.1:8080/health   # Rust server
```

The CLI can talk **directly** to the Python engine (`--engine-url`) or through the Rust server (Web path).

---

### Component Map

#### Rust workspace (`crates/`)

| Crate | Responsibility |
|-------|----------------|
| **likecodex-core** | Shared types: `Config`, `Event`, `Task`, permission models, event bus |
| **likecodex-cli** | Terminal entry: one-shot runs, REPL, Ratatui TUI, optional engine auto-start |
| **likecodex-server** | Axum HTTP server: engine bridge, SSE `/events`, `/execute`, sessions API |
| **likecodex-executor** | Runs shell/git locally inside configured working directory |
| **likecodex-sandbox** | Spawns Docker containers for high-risk commands |
| **likecodex-indexer** | File index and code-graph search (Tree-sitter integration planned) |

#### Python engine (`packages/likecodex-engine/`)

| Module | Responsibility |
|--------|----------------|
| **agent/loop.py** | Core agent loop: stream LLM → parse tool calls → execute → repeat |
| **agent/planner.py** | Optional step-by-step plan before execution |
| **agent/coordinator.py** | Dual-model handoff (planner Pro → executor Flash) |
| **agent/subagent*.py** | Delegate subtasks to focused child agent runs |
| **agent/guards.py** | Loop/storm/repeat guards, empty-final protection |
| **agent/plan_mode.py** | Restrict tools while in read-only planning |
| **tools/** | Built-in tools: filesystem, shell, git, grep, LSP, review, MCP, … |
| **llm/deepseek.py** | DeepSeek V4 provider with cache usage metrics |
| **context/** | Cache-first prompt assembly, compaction, pruning |
| **permissions/** | Approval modes, policy rules, risk classification |
| **persistence/** | SQLite sessions + JSONL event history |
| **memory/** | Optional vector memory (`.likecodex/memory.jsonl`) |

#### Web UI (`web/`)

| Area | Responsibility |
|------|----------------|
| **src/app/page.tsx** | Three-column layout: timeline / chat / diff |
| **src/lib/api.ts** | HTTP client + SSE parser (`parseRustEvent`) |
| **src/lib/store.ts** | Zustand state: messages, tasks, permissions, diffs |

---

### End-to-End Request Flow

Example: user sends *"Add unit tests for utils.py"* in the Web UI.

```text
  Browser                Rust Server (:8080)          Python Engine (:9090)         DeepSeek API
     │                          │                            │                          │
     │  POST /tasks             │                            │                          │
     │ ───────────────────────► │  POST /tasks (forward)     │                          │
     │                          │ ─────────────────────────► │                          │
     │                          │                            │  AgentLoop.run()         │
     │                          │                            │ ────────────────────────►│
     │                          │                            │ ◄────────────────────────│ tool_calls
     │                          │                            │                          │
     │                          │                            │  read_file / write_file  │
     │                          │                            │  run_command (maybe)     │
     │                          │ ◄── engine SSE chunks ──── │                          │
     │                          │  map_engine_output()       │                          │
     │  GET /events (SSE)       │  EventBus.emit()           │                          │
     │ ◄─────────────────────── │                            │                          │
     │  stream_chunk            │                            │                          │
     │  tool_call_requested     │                            │                          │
     │  permission_requested?   │                            │                          │
     │  task_completed          │                            │                          │
```

**Step by step:**

1. **Web/CLI** sends `POST /tasks` or `POST /chat` to Rust server with `{ "prompt": "...", "session_id": "..." }`.
2. **Rust server** creates a client-visible `task_id`, emits `task_started`, and forwards to Python `/tasks` or `/chat`.
3. **Python engine** runs `AgentLoop`:
   - Builds messages from cache-first context (static system prefix + history).
   - Calls DeepSeek with tool schemas.
   - Executes tool calls (possibly in parallel for read-only tools).
   - Streams assistant deltas and tool events.
4. **High-risk shell** (`run_command`) may route to Rust `POST /execute` → Docker sandbox (depends on approval mode).
5. **Rust server** maps flat Python output objects → typed `Event` values → broadcasts on `/events`.
6. **Web/CLI** renders streaming text, tool cards, permission modals, and file diffs.

For permission prompts in `auto` mode, the client calls `POST /permissions/{id}/respond`; the engine resumes the blocked tool call.

---

### Agent Loop (Python Engine)

The heart of LikeCodex is `AgentLoop` in `packages/likecodex-engine/likecodex_engine/agent/loop.py`:

```text
┌──────────────┐
│ User prompt  │
└──────┬───────┘
       ▼
┌──────────────────────────────────────┐
│ Build context (CacheFirstContext)    │
│   SYSTEM prefix + history + [Context]│
└──────┬───────────────────────────────┘
       ▼
┌──────────────────────────────────────┐
│ LLM.complete / stream (DeepSeek V4)  │
└──────┬───────────────────────────────┘
       │
       ├── text only ──► final answer ──► done
       │
       └── tool_calls ──► permission check
                │
                ├── denied ──► error to model ──► retry loop
                │
                └── allowed ──► execute tools (local / sandbox)
                         │
                         └── append tool results ──► loop again
```

**Notable behaviors:**

- **Guards** — detects infinite loops, repeated failures, storm of tool calls.
- **Compaction** — when context nears token limit, summarizes tail while preserving SYSTEM prefix.
- **Sub-agents** — `task` tool spawns isolated runs with separate context.
- **Checkpoints** — snapshots files before write tools; `/rewind` restores state.
- **Plan mode** — blocks mutating tools until user exits planning.

---

### Event Protocol (SSE)

All clients consume **adjacently tagged JSON** on `GET /events`:

```json
{"type":"stream_chunk","payload":{"task_id":"…","content":"partial text"}}
{"type":"tool_call_requested","payload":{"task_id":"…","call":{"id":"…","name":"read_file","arguments":{…}}}}
{"type":"permission_requested","payload":{"task_id":"…","request":{…}}}
{"type":"task_completed","payload":{"id":"…","status":"completed"}}
```

Python emits flat objects like `{"type":"assistant","content":"…"}`; **`likecodex-server`** maps them to structured events via `event_mapping.rs` so CLI, TUI, and Web stay in sync.

Full schema: [docs/EVENTS.md](docs/EVENTS.md)

---

### Cache-First Context Model

DeepSeek **automatic context caching** requires the prompt prefix (from token 0) to be **byte-identical** across turns. LikeCodex treats cache stability as a design invariant.

```text
┌─────────────────────────────────────────┐
│ IMMUTABLE PREFIX (never changes mid-session) │
│   system.md + skills + project memory   │
│   + sorted tool JSON schemas            │
├─────────────────────────────────────────┤
│ APPEND-ONLY LOG                         │
│   user → assistant → tool → …           │
├─────────────────────────────────────────┤
│ VOLATILE SCRATCH (not sent to API)      │
│   planner raw output, debug traces      │
└─────────────────────────────────────────┘
```

| Technique | Purpose |
|-----------|---------|
| Versioned `system.md` (>1024 tokens) | Stable SYSTEM message |
| Sorted tool schema keys | Deterministic `tools` parameter |
| `[Context]` USER messages at tail | Dynamic memory without touching prefix |
| Session reuse via `session_id` | Same `ContextManager` across HTTP requests |
| Tail-only compaction | Trim history without editing SYSTEM block |

Monitor cache metrics:

```bash
curl http://127.0.0.1:9090/metrics
curl http://127.0.0.1:8080/metrics
```

Web UI header shows live cache hit %. Full spec: [docs/SPEC-CACHE.md](docs/SPEC-CACHE.md)

---

### Security and Execution Routing

| Approval mode | Read tools | Write / medium shell | High-risk shell | Notes |
|---------------|------------|----------------------|-----------------|-------|
| `read-only` | Allowed | Blocked | Blocked | Safe analysis |
| `auto` | Auto | User prompt | Docker sandbox | Default; fallback if Docker down |
| `full-access` | Auto | Auto | Local | Trusted environments only |
| `sandbox-required` | Auto | Sandbox only | Sandbox only | CI / untrusted prompts |

**Layers:**

- **Path confinement** — file/git tools cannot escape `LIKECODEX_WORKING_DIR`.
- **Risk classifier** — shell commands tagged read / medium / high.
- **Policy rules** — allow / ask / deny per tool in config.
- **Docker sandbox** — isolated container with resource limits.
- **API token** — optional Bearer auth on `POST /execute`.
- **Config redaction** — secrets never returned from `/config`.

Details: [SECURITY.md](SECURITY.md)

---

## Features

### Interfaces

| Interface | Command / URL | Best for |
|-----------|---------------|----------|
| One-shot CLI | `cargo run -p likecodex-cli -- "prompt"` | Scripts, CI, quick tasks |
| Interactive REPL | `likecodex interactive` | Lightweight terminal chat |
| Ratatui TUI | `likecodex --tui` | Rich terminal with streaming |
| Web UI | http://localhost:3000 | Chat, diffs, permissions, sessions |

### Agent Capabilities

- Multi-turn **tool-calling loop** with structured results
- Optional **task planner** (`LIKECODEX_ENABLE_PLANNER=true`)
- **Sub-agent orchestration** for delegated subtasks
- **MCP integration** for external tool servers
- **Session persistence** (SQLite + JSONL events)
- **Vector memory** (optional `.likecodex/memory.jsonl`)
- **Checkpoints & rewind** before destructive writes
- **Slash commands** (`/compact`, `/init`, …)

### Models (DeepSeek V4)

| Model | Config | Notes |
|-------|--------|-------|
| `deepseek-v4-flash` | Default | Fast, lowest cost, best cache economics |
| `deepseek-v4-pro` | Planner / hard tasks | Higher quality |

Set `DEEPSEEK_API_KEY` or `LIKECODEX_LLM_API_KEY`. Enable thinking: `LIKECODEX_DEEPSEEK_THINKING=true`.

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| [Rust](https://rustup.rs/) | 1.70+ | CLI, server, sandbox, executor |
| [Python](https://www.python.org/) | 3.11+ | Agent engine |
| [uv](https://github.com/astral-sh/uv) | latest | Python deps |
| [Node.js](https://nodejs.org/) | 20+ | Web UI |
| [Docker](https://www.docker.com/products/docker-desktop/) | optional | Sandbox execution |

**Platform notes:**

- **Windows:** use `scripts/dev.ps1`; Rust needs **MSVC Build Tools** — run `.\scripts\check-prerequisites.ps1`
- **macOS / Linux:** use `scripts/dev.sh`
- **Sandbox:** `docker build -t likecodex/sandbox:latest docker/sandbox`

---

## Installation

```bash
git clone https://github.com/JasonBuildAI/likecodex.git
cd likecodex

uv sync --all-packages --extra dev
cd web && npm install --legacy-peer-deps && cd ..
cargo build --workspace

cp .env.example .env
# Edit .env — set DEEPSEEK_API_KEY
```

Create `~/.likecodex/config.toml` (see [Configuration](#configuration)).

---

## Quick Start

### 1. Configure LLM

`~/.likecodex/config.toml`:

```toml
[llm]
provider = "deepseek"
model = "deepseek-v4-flash"
api_key = "..."               # or DEEPSEEK_API_KEY in .env
base_url = "https://api.deepseek.com"

[deepseek]
thinking = false

[approval]
mode = "auto"

[sandbox]
enabled = true
image = "likecodex/sandbox:latest"
allow_fallback = true

[server]
host = "127.0.0.1"
port = 8080
engine_url = "http://127.0.0.1:9090"
```

### 2. Start dev stack

```bash
./scripts/dev.sh          # macOS / Linux
.\scripts\dev.ps1         # Windows
.\scripts\dev.ps1 -SkipWeb   # engine + server only
```

### 3. Run a task

```bash
cargo run -p likecodex-cli -- "Create hello.py that prints 1..10 and run it"
cargo run -p likecodex-cli -- --tui
# or open http://localhost:3000
```

---

## Usage

### CLI & TUI

```bash
cargo run -p likecodex-cli -- "refactor the login module"
cargo run -p likecodex-cli -- run "fix failing tests"
cargo run -p likecodex-cli -- interactive
cargo run -p likecodex-cli -- --tui
cargo run -p likecodex-cli -- serve
cargo run -p likecodex-cli -- config

# Overrides
cargo run -p likecodex-cli -- --approval read-only "analyze repo"
cargo run -p likecodex-cli -- --engine-url http://127.0.0.1:9090 "prompt"
```

### Web UI

Three columns: **sessions & tasks** | **streaming chat** | **file diff viewer**.

Features: permission modal, live SSE, cache hit % in header, session history.

### HTTP API

**Rust server (`:8080`)** — primary entry for Web and integrations:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/config` | Redacted config |
| POST | `/tasks` | Background agent task |
| POST | `/chat` | Streaming chat (SSE) |
| GET | `/events` | Global SSE event stream |
| GET/POST | `/permissions/*` | Approval workflow |
| POST | `/execute` | Sandbox command |
| GET | `/sessions` | List sessions |

**Python engine (`:9090`)** — direct CLI access or via bridge:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/run` | Synchronous execution |
| POST | `/chat` | Streaming SSE |
| POST | `/plan` | Plan only |
| POST | `/tasks` | Background task |
| GET | `/metrics` | Cache metrics |

Examples:

```bash
curl -X POST http://127.0.0.1:8080/tasks \
  -H "Content-Type: application/json" \
  -d '{"prompt": "List all Python files"}'

curl -N http://127.0.0.1:8080/events
```

Full reference: [docs/API.md](docs/API.md)

---

## Built-in Tools

| Category | Tools |
|----------|-------|
| Filesystem | `read_file`, `write_file`, `list_dir`, `search_files`, `edit_file` |
| Shell | `run_command`, background job helpers |
| Search | `grep_files`, `find_symbol`, `index_search`, LSP tools |
| Git | `git_status`, `git_diff`, `git_log`, `git_branch`, `git_commit` |
| Review | `review_file`, `review_diff`, `check_dependencies` |
| Agent | `task`, `parallel_tasks`, `remember` / `forget`, `todo` |

Enable MCP: `LIKECODEX_ENABLE_MCP=true` + `[mcp.servers.*]` in config.

---

## Configuration

Priority (low → high): code defaults → `~/.likecodex/config.toml` → env vars → CLI flags.

Key environment variables — see [.env.example](.env.example):

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | — | API key |
| `LIKECODEX_LLM_MODEL` | `deepseek-v4-flash` | Model |
| `LIKECODEX_WORKING_DIR` | `.` | Agent workspace root |
| `LIKECODEX_APPROVAL_MODE` | `auto` | Approval mode |
| `LIKECODEX_ENABLE_PLANNER` | `false` | Task planner |
| `LIKECODEX_SESSION_DB` | `.likecodex/sessions.db` | Session database |

---

## Development

```bash
cargo fmt --all && cargo clippy --workspace --all-targets -- -D warnings
uv run ruff check packages/likecodex-engine tests
cd web && npm run lint && npm run type-check

# Run services individually
uv run python -m likecodex_engine.server    # :9090
cargo run -p likecodex-server                # :8080
cd web && npm run dev                          # :3000
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Testing

```bash
# Rust
cargo test --workspace

# Python (exclude integration unless Rust server is built)
uv sync --all-packages --extra dev
uv run pytest packages/likecodex-engine/tests tests -m "not integration" -v

# Full-stack E2E (needs cargo build -p likecodex-server)
uv run pytest tests/e2e/test_full_stack.py -m integration -v
uv run python scripts/smoke_test.py

# Web
cd web && npm run test && npm run build

# Benchmarks
uv run python benchmarks/cache/run.py --turns 10 --simulate-cache
uv run python benchmarks/agent/run.py --check
```

CI runs these on every push — see [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## Project Layout

```text
likecodex/
├── crates/                    # Rust workspace
│   ├── likecodex-core/        # Shared types, config, events
│   ├── likecodex-cli/         # CLI + TUI
│   ├── likecodex-server/      # HTTP/SSE bridge
│   ├── likecodex-executor/    # Local execution
│   ├── likecodex-sandbox/     # Docker sandbox
│   └── likecodex-indexer/     # File/code search
├── packages/likecodex-engine/ # Python agent core
├── web/                       # Next.js UI
├── tests/                     # Integration & security tests
├── scripts/                   # dev.sh, dev.ps1, smoke_test.py
├── benchmarks/                # Cache & agent regression gates
├── docs/                      # Architecture, API, events, cache spec
└── docker/                    # Sandbox & server images
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [README.zh-CN.md](README.zh-CN.md) | Chinese documentation |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architecture deep dive |
| [docs/SPEC-CACHE.md](docs/SPEC-CACHE.md) | Cache-first context spec |
| [docs/API.md](docs/API.md) | HTTP API reference |
| [docs/EVENTS.md](docs/EVENTS.md) | SSE event schema |
| [docs/USAGE.md](docs/USAGE.md) | Detailed usage guide |
| [docs/PARITY-CHECKLIST.md](docs/PARITY-CHECKLIST.md) | Feature ↔ test mapping |
| [SECURITY.md](SECURITY.md) | Security policy |

---

## Roadmap

- [ ] Tree-sitter symbol indexing in `likecodex-indexer`
- [ ] MCP SSE/WebSocket transports
- [ ] Production deployment guides (Docker Compose, Kubernetes)
- [ ] Plugin marketplace for custom tools
- [ ] Additional LLM providers (Azure OpenAI, local Ollama)

---

## Contributing & License

Contributions welcome! Read [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

Licensed under the [MIT License](LICENSE).

Inspired by OpenAI Codex and the broader agentic coding ecosystem.
