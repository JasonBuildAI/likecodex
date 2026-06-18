# LikeCodex

[![CI](https://github.com/JasonBuildAI/likecodex/actions/workflows/ci.yml/badge.svg)](https://github.com/JasonBuildAI/likecodex/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Rust](https://img.shields.io/badge/rust-1.70+-orange.svg)](https://www.rust-lang.org/)
[![Node.js 20+](https://img.shields.io/badge/node.js-20+-green.svg)](https://nodejs.org/)

**LikeCodex** is a production-oriented, open-source coding agent inspired by [OpenAI Codex](https://openai.com/index/introducing-codex/). It combines a **Rust control plane** (CLI, HTTP API, sandbox execution) with a **Python agent engine** (LLM loop, tools, planning, memory) and a **Next.js web UI** — giving you terminal, TUI, and browser interfaces over the same event stream.

**[中文文档 README.zh-CN.md](README.zh-CN.md)**

---

## Table of Contents

- [Why LikeCodex?](#why-likecodex)
- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [CLI & TUI](#cli--tui)
  - [Web UI](#web-ui)
  - [HTTP API](#http-api)
- [Built-in Tools](#built-in-tools)
- [Configuration](#configuration)
- [Security & Approval Modes](#security--approval-modes)
- [Project Structure](#project-structure)
- [Development](#development)
- [Testing](#testing)
- [Docker](#docker)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [Roadmap](#roadmap)
- [Contributing & License](#contributing--license)

---

## Why LikeCodex?

Most coding agents are either a thin CLI wrapper around an LLM or a monolithic Python app. LikeCodex splits responsibilities deliberately:

| Layer | Technology | Responsibility |
|-------|------------|----------------|
| **Interface** | Rust CLI/TUI, Next.js Web | User interaction, streaming display |
| **Bridge** | Rust Axum server | HTTP/SSE, permissions, session API |
| **Brain** | Python engine | Agent loop, LLM calls, tool orchestration |
| **Execution** | Rust executor + Docker sandbox | Shell/git with path confinement |

This hybrid design gives you **fast, safe execution** in Rust and **rapid agent iteration** in Python, while CLI and Web share the same normalized SSE event protocol.

---

## Features

### Interfaces

| Interface | Command / URL | Best for |
|-----------|---------------|----------|
| **One-shot CLI** | `cargo run -p likecodex-cli -- "prompt"` | Scripts, CI, quick tasks |
| **Interactive REPL** | `likecodex interactive` | Lightweight terminal chat |
| **Ratatui TUI** | `likecodex --tui` | Rich terminal UI with streaming |
| **Web UI** | http://localhost:3000 | Chat, diffs, permissions, session history |

### Agent Capabilities

- **Tool-calling loop** — multi-turn reasoning with structured tool results
- **Task planner** — optional step-by-step plan before execution (`LIKECODEX_ENABLE_PLANNER=true`)
- **Sub-agent orchestration** — delegate subtasks to focused agent runs
- **MCP integration** — register external tools via Model Context Protocol servers
- **Session persistence** — SQLite-backed sessions with JSONL event history
- **Vector memory** — optional long-term memory store (`.likecodex/memory.jsonl`)

### Models

| Provider | Config value | Notes |
|----------|--------------|-------|
| OpenAI | `provider = "openai"` | GPT-4o and compatible models |
| Anthropic | `provider = "anthropic"` | Claude models |
| Mock | `provider = "mock"` | Deterministic responses for tests |

API keys resolve from `config.toml` or `{PROVIDER}_API_KEY` environment variables.

---

## Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                        User Interfaces                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ CLI / REPL  │  │  Ratatui    │  │   Next.js Web UI    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
└─────────┼────────────────┼─────────────────────┼────────────┘
          │                │                     │
          └────────────────┼─────────────────────┘
                           │  HTTP / SSE
                ┌──────────▼──────────┐
                │   Rust API Server   │  :8080
                │   (likecodex-server)│
                │   • /tasks /chat    │
                │   • /events (SSE)   │
                │   • /permissions    │
                │   • /execute        │
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │   Python Engine     │  :9090
                │ (likecodex-engine)  │
                │   • AgentLoop       │
                │   • ToolRegistry    │
                │   • LLM providers   │
                └──────────┬──────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
┌─────────▼────────┐ ┌─────▼─────┐ ┌───────▼────────┐
│ Local Executor   │ │  Docker   │ │ File Indexer   │
│ (shell, git)     │ │  Sandbox  │ │ (search)       │
└──────────────────┘ └───────────┘ └────────────────┘
```

**Request flow (Web chat example):**

1. Browser sends `POST /tasks` or `POST /chat` to Rust server (`:8080`)
2. Rust server forwards to Python engine (`:9090`)
3. Engine runs the agent loop, calling tools (filesystem, shell, git, …)
4. High-risk shell commands route to Docker sandbox via `POST /execute`
5. Events stream back over `GET /events` (SSE) to Web/CLI
6. Permission prompts appear when approval mode requires user consent

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for component-level details.

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| [Rust](https://rustup.rs/) | 1.70+ | CLI, server, sandbox, executor |
| [Python](https://www.python.org/) | 3.11+ | Agent engine |
| [uv](https://github.com/astral-sh/uv) | latest | Python dependency management |
| [Node.js](https://nodejs.org/) | 20+ | Web UI |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | optional | Isolated command execution |

**Platform notes:**

- **Windows**: Use `scripts/dev.ps1`; Rust linker may require MSVC Build Tools
- **macOS / Linux**: Use `scripts/dev.sh`
- **Sandbox**: Build the image once — `docker build -t likecodex/sandbox:latest docker/sandbox`

---

## Installation

```bash
git clone https://github.com/JasonBuildAI/likecodex.git
cd likecodex

# Python dependencies
uv sync --all-packages

# Web dependencies
cd web && npm install --legacy-peer-deps && cd ..

# Rust workspace (release build optional)
cargo build --workspace
```

Copy the environment template:

```bash
cp .env.example .env
# Edit .env with your API keys
```

Create user config at `~/.likecodex/config.toml` (see [Configuration](#configuration)).

---

## Quick Start

### 1. Configure LLM

`~/.likecodex/config.toml`:

```toml
[llm]
provider = "openai"
model = "gpt-4o"
api_key = "sk-..."          # or set OPENAI_API_KEY in .env
temperature = 0.0
max_tokens = 4096

[approval]
mode = "auto"               # read-only | auto | full-access | sandbox-required

[sandbox]
enabled = true
image = "likecodex/sandbox:latest"
allow_fallback = true       # set false when using sandbox-required
timeout_secs = 120
memory_mb = 512

[server]
host = "127.0.0.1"
port = 8080
engine_url = "http://127.0.0.1:9090"
# api_token = "your-local-token"   # protects POST /execute
```

### 2. Start the dev stack

```bash
# macOS / Linux
./scripts/dev.sh

# Windows PowerShell
.\scripts\dev.ps1

# Skip Web UI only
.\scripts\dev.ps1 -SkipWeb

# Engine + server only (no Web)
.\scripts\dev.ps1 -SkipWeb
```

| Service | URL | Description |
|---------|-----|-------------|
| Python Engine | http://127.0.0.1:9090 | Agent loop, tools, LLM |
| Rust API Server | http://127.0.0.1:8080 | Bridge, SSE, sandbox, sessions |
| Web UI | http://localhost:3000 | Browser chat interface |

Verify health:

```bash
curl http://127.0.0.1:9090/health   # Python engine
curl http://127.0.0.1:8080/health   # Rust server
```

### 3. Run your first task

```bash
# One-shot: create and run a script
cargo run -p likecodex-cli -- "Create a Python script that prints numbers 1 to 10, then run it"

# Interactive TUI
cargo run -p likecodex-cli -- --tui

# Or open http://localhost:3000 and type your prompt
```

---

## Usage

### CLI & TUI

```bash
# One-shot prompt (positional argument)
cargo run -p likecodex-cli -- "refactor the login module"

# Subcommands
cargo run -p likecodex-cli -- run "fix the failing test"
cargo run -p likecodex-cli -- interactive    # plain REPL
cargo run -p likecodex-cli -- --tui          # Ratatui terminal UI
cargo run -p likecodex-cli -- serve          # start Rust API server only
cargo run -p likecodex-cli -- config         # print redacted config

# Overrides
cargo run -p likecodex-cli -- --approval read-only "analyze this repo"
cargo run -p likecodex-cli -- --config /path/to/config.toml "prompt"
cargo run -p likecodex-cli -- --engine-url http://127.0.0.1:9090 "prompt"
```

When the agent requests permission (in `auto` mode), the CLI prompts you in-terminal. Approve or deny; the engine continues automatically.

### Web UI

The Web UI provides a three-column layout:

| Column | Content |
|--------|---------|
| **Left** | Session list, task timeline, plan steps |
| **Center** | Streaming chat messages |
| **Right** | Diff viewer for file changes |

Additional features:

- **Permission modal** — approve/deny tool calls when approval mode requires it
- **Live SSE** — subscribes to `GET /events` for real-time updates
- **Session history** — reload past conversations from SQLite

Set `NEXT_PUBLIC_API_BASE=/api` (dev proxy) or point to `http://127.0.0.1:8080` in production.

### HTTP API

**Rust server** (`:8080`) — primary API for Web and external integrations:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/config` | Redacted configuration |
| POST | `/tasks` | Create background agent task |
| POST | `/chat` | Stream chat (SSE response) |
| GET | `/events` | Global SSE event stream |
| GET | `/permissions/pending` | Pending approval requests |
| POST | `/permissions/{id}/respond` | Approve or deny |
| POST | `/execute` | Sandbox command (Bearer token if configured) |
| GET | `/sessions` | List persisted sessions |
| GET | `/sessions/{id}/events` | Session event history |
| GET | `/index/search?pattern=` | Filename index search |

**Python engine** (`:9090`) — used directly by CLI or via Rust bridge:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/run` | Synchronous prompt execution |
| POST | `/chat` | Streaming agent output (SSE) |
| POST | `/plan` | Generate plan without executing |
| POST | `/tasks` | Background task |
| GET | `/tasks/{id}` | Task status and outputs |

Example — create a task:

```bash
curl -X POST http://127.0.0.1:8080/tasks \
  -H "Content-Type: application/json" \
  -d '{"prompt": "List all Python files in the project"}'
```

Example — subscribe to events:

```bash
curl -N http://127.0.0.1:8080/events
```

Full reference: [docs/API.md](docs/API.md) · Event schema: [docs/EVENTS.md](docs/EVENTS.md)

---

## Built-in Tools

The Python engine registers these tools by default:

| Category | Tool | Description |
|----------|------|-------------|
| **Filesystem** | `read_file` | Read file contents (path-confined) |
| | `write_file` | Write or create files |
| | `list_dir` | List directory entries |
| | `search_files` | Glob-style file search |
| **Shell** | `run_command` | Execute shell commands (approval + sandbox routing) |
| **Search** | `grep_files` | Regex search across files |
| | `find_symbol` | Symbol lookup (index-assisted) |
| | `index_search` | Query Rust indexer service |
| **Git** | `git_status`, `git_diff`, `git_log`, `git_branch`, `git_commit` | Git operations |
| **Review** | `review_file`, `review_diff`, `check_dependencies` | Code review helpers |

Enable MCP tools by setting `LIKECODEX_ENABLE_MCP=true` and configuring servers in `config.toml`:

```toml
[mcp.servers.filesystem]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/root"]
```

---

## Configuration

Configuration merges from (highest priority last):

1. Defaults in code
2. `~/.likecodex/config.toml`
3. Environment variables (`.env` or shell)
4. CLI flags (`--approval`, `--config`, `--engine-url`)

### config.toml sections

| Section | Key fields |
|---------|------------|
| `[llm]` | `provider`, `model`, `api_key`, `base_url`, `temperature`, `max_tokens` |
| `[approval]` | `mode` |
| `[sandbox]` | `enabled`, `image`, `allow_fallback`, `timeout_secs`, `memory_mb`, `max_cpus`, `writable_roots` |
| `[server]` | `host`, `port`, `engine_url`, `api_token` |
| `[mcp.servers.*]` | `command`, `args`, `env` |

### Environment variables

See [.env.example](.env.example):

| Variable | Default | Description |
|----------|---------|-------------|
| `LIKECODEX_LLM_PROVIDER` | `openai` | LLM provider name |
| `LIKECODEX_LLM_MODEL` | `gpt-4o` | Model identifier |
| `LIKECODEX_LLM_API_KEY` | — | API key (also `OPENAI_API_KEY`) |
| `LIKECODEX_ENGINE_URL` | `http://127.0.0.1:9090` | Python engine base URL |
| `LIKECODEX_ENGINE_HOST` | `127.0.0.1` | Engine bind host |
| `LIKECODEX_ENGINE_PORT` | `9090` | Engine bind port |
| `LIKECODEX_WORKING_DIR` | `.` | Agent working directory |
| `LIKECODEX_APPROVAL_MODE` | `auto` | Override approval mode |
| `LIKECODEX_API_TOKEN` | — | Bearer token for `/execute` |
| `LIKECODEX_SANDBOX_URL` | `http://127.0.0.1:8080/execute` | Sandbox endpoint |
| `LIKECODEX_ENABLE_PLANNER` | `false` | Enable task planner |
| `LIKECODEX_ENABLE_MCP` | `false` | Register MCP tool servers |
| `LIKECODEX_MEMORY_PATH` | `.likecodex/memory.jsonl` | Vector memory file |
| `LIKECODEX_SESSION_DB` | `.likecodex/sessions.db` | SQLite session database |
| `NEXT_PUBLIC_API_BASE` | `/api` | Web UI API base URL |

---

## Security & Approval Modes

LikeCodex applies defense in depth:

- **Path confinement** — filesystem and git tools cannot escape the configured working directory
- **Command classification** — shell tools assign risk levels (read / medium / high)
- **User approval** — medium-risk operations prompt in CLI or Web
- **Docker sandbox** — high-risk commands run in an isolated container
- **API token** — optional Bearer auth on `POST /execute`
- **Config redaction** — `/config` and `likecodex config` never expose raw secrets

### Approval modes

| Mode | Read tools | Write / shell | High-risk shell | Fallback |
|------|------------|---------------|-----------------|----------|
| `read-only` | ✅ | ❌ blocked | ❌ blocked | — |
| `auto` | ✅ auto | ⚠️ prompt | 🐳 sandbox | ✅ if Docker down |
| `full-access` | ✅ auto | ✅ auto | ✅ local | — |
| `sandbox-required` | ✅ auto | 🐳 sandbox only | 🐳 sandbox only | ❌ no fallback |

For untrusted prompts or CI on shared runners, prefer `sandbox-required` with `allow_fallback = false`.

Report vulnerabilities: [SECURITY.md](SECURITY.md)

---

## Project Structure

```text
likecodex/
├── crates/                         # Rust workspace
│   ├── likecodex-core/             # Shared types, config, events
│   ├── likecodex-cli/              # CLI + Ratatui TUI
│   ├── likecodex-server/           # Axum HTTP/SSE bridge
│   ├── likecodex-executor/         # Local command execution
│   ├── likecodex-sandbox/          # Docker sandbox orchestration
│   └── likecodex-indexer/          # File index search
├── packages/
│   └── likecodex-engine/           # Python agent core
│       └── likecodex_engine/
│           ├── agent/              # Agent loop, planner, permissions
│           ├── tools/              # Filesystem, shell, git, review
│           ├── llm/                # OpenAI, Anthropic, mock providers
│           ├── context/            # Prompt assembly
│           └── memory/             # Session + vector memory
├── web/                            # Next.js frontend
│   └── src/
│       ├── app/                    # Pages
│       ├── components/             # Chat, DiffViewer, PermissionModal
│       └── lib/                    # API client, SSE, Zustand store
├── docs/                           # Architecture, API, events, usage
├── tests/                          # Integration & security tests
├── docker/                         # Sandbox & server Dockerfiles
├── scripts/                        # dev.sh, dev.ps1
├── .github/workflows/              # CI pipeline
├── docker-compose.yml              # Experimental full stack
├── .env.example                    # Environment template
├── CONTRIBUTING.md
├── SECURITY.md
└── CHANGELOG.md
```

---

## Development

```bash
# Format & lint Rust
cargo fmt --all
cargo clippy --workspace --all-targets -- -D warnings

# Python lint
uv run ruff check packages/likecodex-engine tests

# Web lint
cd web && npm run lint && npm run type-check

# Run individual services manually
uv run python -m likecodex_engine.server          # :9090
cargo run -p likecodex-server                     # :8080
cd web && npm run dev                             # :3000
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for PR guidelines and commit conventions.

---

## Testing

```bash
# Rust unit & integration tests
cargo test --workspace

# Python tests
uv sync --all-packages
uv run pytest packages/likecodex-engine/tests tests -v

# Web tests
cd web && npm install --legacy-peer-deps && npm run test

# Full CI locally (approximate)
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
uv run pytest packages/likecodex-engine/tests tests -v
cd web && npm run lint && npm run type-check && npm run test && npm run build
```

---

## Docker

```bash
# Build sandbox image (required for sandbox modes)
docker build -t likecodex/sandbox:latest docker/sandbox

# Experimental full stack
docker compose up
```

Services defined in `docker-compose.yml`: `engine` (:9090), `server` (:8080), `web` (:3000).

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|--------------|-----|
| `failed to connect to LikeCodex engine` | Engine not running | Start `dev.ps1` / `dev.sh` or run engine manually |
| `engine error: ... api_key` | Missing LLM key | Set key in `config.toml` or `.env` |
| Sandbox commands fail | Docker not running / image missing | Start Docker; build sandbox image |
| Web shows no events | Server not reachable | Check `:8080/health`; verify `NEXT_PUBLIC_API_BASE` |
| Permission stuck | No UI/CLI response | Approve in Web modal or CLI prompt |
| Rust build fails on Windows | Missing MSVC linker | Install [Build Tools for Visual Studio](https://visualstudio.microsoft.com/visual-cpp-build-tools/) |

Enable verbose logs:

```bash
RUST_LOG=debug cargo run -p likecodex-server
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [README.zh-CN.md](README.zh-CN.md) | Chinese documentation |
| [docs/USAGE.md](docs/USAGE.md) | Detailed usage guide |
| [docs/API.md](docs/API.md) | HTTP API reference |
| [docs/EVENTS.md](docs/EVENTS.md) | SSE event schema |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution guide |
| [SECURITY.md](SECURITY.md) | Security policy |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

---

## Roadmap

- [ ] Tree-sitter symbol indexing in `likecodex-indexer`
- [ ] MCP SSE/WebSocket transports
- [ ] Production deployment guides (Docker Compose, Kubernetes)
- [ ] Plugin marketplace for custom tools
- [ ] Additional LLM providers (Azure OpenAI, local Ollama)

---

## Contributing & License

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before opening a PR.

This project is licensed under the [MIT License](LICENSE).

---

## Acknowledgments

Inspired by OpenAI Codex and the broader agentic coding ecosystem. Built with Rust, Python, and Next.js.
