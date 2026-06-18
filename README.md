# LikeCodex

[![CI](https://github.com/JasonBuildAI/likecodex/actions/workflows/ci.yml/badge.svg)](https://github.com/JasonBuildAI/likecodex/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Rust](https://img.shields.io/badge/rust-1.70+-orange.svg)](https://www.rust-lang.org/)

**LikeCodex** is a production-oriented, open-source coding agent inspired by OpenAI Codex. It combines a **Rust control plane** (CLI, API server, sandbox) with a **Python agent engine** (LLM loop, tools, planning) and a **Next.js web UI**.

[中文文档](README.zh-CN.md) · [Architecture](docs/ARCHITECTURE.md) · [API Reference](docs/API.md) · [Contributing](CONTRIBUTING.md)

---

## Features

| Category | Capabilities |
|----------|-------------|
| **Interfaces** | CLI one-shot, interactive REPL, Ratatui TUI, Web chat UI |
| **Agent** | Tool-calling loop, task planner, sub-agent orchestration |
| **Tools** | Filesystem, shell, git, grep, code review, MCP integration |
| **Security** | Approval modes, path confinement, Docker sandbox, API token |
| **Memory** | SQLite sessions, JSONL/vector memory, event streaming (SSE) |
| **Models** | OpenAI, Anthropic, mock provider for tests |

---

## Architecture

```text
┌─────────────┐     ┌─────────────┐
│  CLI / TUI  │     │   Web UI    │
└──────┬──────┘     └──────┬──────┘
       │                   │
       └─────────┬─────────┘
                 │  HTTP / SSE
       ┌─────────▼─────────┐
       │  Rust API Server  │  :8080
       │  (Axum bridge)    │
       └─────────┬─────────┘
                 │
       ┌─────────▼─────────┐
       │  Python Engine    │  :9090
       │  AgentLoop + Tools│
       └─────────┬─────────┘
                 │
       ┌─────────▼─────────┐
       │ Sandbox / Executor│
       │ Docker + local    │
       └───────────────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.

---

## Quick Start

### Prerequisites

- [Rust](https://rustup.rs/) toolchain
- [Python 3.11+](https://www.python.org/) and [uv](https://github.com/astral-sh/uv)
- [Node.js 20+](https://nodejs.org/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (optional, for sandbox)

### 1. Clone & configure

```bash
git clone https://github.com/JasonBuildAI/likecodex.git
cd likecodex
cp .env.example .env
```

Create `~/.likecodex/config.toml`:

```toml
[llm]
provider = "openai"
model = "gpt-4o"
api_key = "sk-..."

[approval]
mode = "auto"  # read-only | auto | full-access | sandbox-required

[sandbox]
enabled = true
allow_fallback = true

[server]
host = "127.0.0.1"
port = 8080
engine_url = "http://127.0.0.1:9090"
# api_token = "your-local-token"  # optional, protects /execute
```

### 2. Start development stack

```bash
# macOS / Linux
./scripts/dev.sh

# Windows PowerShell
.\scripts\dev.ps1
```

| Service | URL |
|---------|-----|
| Python Engine | http://127.0.0.1:9090 |
| Rust API Server | http://127.0.0.1:8080 |
| Web UI | http://localhost:3000 |

### 3. Run your first task

```bash
# One-shot CLI
cargo run -p likecodex-cli -- "Create a Python script that prints 1..10 and run it"

# Interactive TUI
cargo run -p likecodex-cli -- --tui

# Or open the Web UI at http://localhost:3000
```

---

## Project Structure

```text
likecodex/
├── crates/                  # Rust workspace
│   ├── likecodex-core/      # Shared types, config, events
│   ├── likecodex-cli/       # CLI + TUI
│   ├── likecodex-server/    # HTTP/SSE API bridge
│   ├── likecodex-executor/  # Local command execution
│   ├── likecodex-sandbox/   # Docker sandbox
│   └── likecodex-indexer/   # File index search
├── packages/
│   └── likecodex-engine/    # Python agent core
├── web/                     # Next.js frontend
├── docs/                    # Architecture, API, events
├── tests/                   # Integration & security tests
├── docker/                  # Sandbox & server Dockerfiles
└── scripts/                 # Dev launchers
```

---

## Configuration

Environment variables (see [.env.example](.env.example)):

| Variable | Default | Description |
|----------|---------|-------------|
| `LIKECODEX_LLM_PROVIDER` | `openai` | LLM provider |
| `LIKECODEX_LLM_MODEL` | `gpt-4o` | Model name |
| `LIKECODEX_APPROVAL_MODE` | `auto` | Permission mode |
| `LIKECODEX_ENGINE_URL` | `http://127.0.0.1:9090` | Python engine URL |
| `LIKECODEX_SANDBOX_URL` | `http://127.0.0.1:8080/execute` | Sandbox endpoint |
| `LIKECODEX_ENABLE_PLANNER` | `false` | Enable task planner |
| `LIKECODEX_ENABLE_MCP` | `false` | Register MCP tools |

---

## Approval Modes

| Mode | Behavior |
|------|----------|
| `read-only` | Read-only tools only |
| `auto` | Low-risk auto; medium-risk prompts; high-risk sandbox |
| `full-access` | All tools run locally without prompts |
| `sandbox-required` | Non-read operations must use sandbox; no fallback |

---

## Docker

```bash
# Build sandbox image
docker build -t likecodex/sandbox:latest docker/sandbox

# Full stack (experimental)
docker compose up
```

---

## Testing

```bash
# Rust
cargo test --workspace

# Python
uv sync --all-packages
uv run pytest packages/likecodex-engine/tests tests -v

# Web
cd web && npm install --legacy-peer-deps && npm run test
```

---

## Documentation

- [Usage Guide](docs/USAGE.md)
- [API Reference](docs/API.md)
- [Event Schema (SSE)](docs/EVENTS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security Policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

---

## Roadmap

- [ ] Tree-sitter symbol indexing
- [ ] MCP SSE/WebSocket transports
- [ ] Production deployment guides (K8s)
- [ ] Plugin marketplace for custom tools

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before opening a PR.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Acknowledgments

Inspired by OpenAI Codex and the broader agentic coding ecosystem. Built with Rust, Python, and Next.js.
