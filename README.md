# LikeCodex

[![CI](https://github.com/JasonBuildAI/likecodex/actions/workflows/ci.yml/badge.svg)](https://github.com/JasonBuildAI/likecodex/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/likecodex)](https://pypi.org/project/likecodex/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/likecodex)](https://pypi.org/project/likecodex/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Rust](https://img.shields.io/badge/rust-1.70+-orange.svg)](https://www.rust-lang.org/)
[![Node.js 20+](https://img.shields.io/badge/node.js-20+-green.svg)](https://nodejs.org/)

**LikeCodex** is an open-source **AI coding assistant** natively powered by **DeepSeek V4**. Describe a task in natural language, and LikeCodex understands your codebase, executes commands, edits files, and reports back — with optional human approval for risky operations.

> [中文文档](README.zh-CN.md)

---

## 📖 Table of Contents

- [Introduction](#introduction)
- [Key Features](#key-features)
- [Architecture Overview](#architecture-overview)
- [Three Agent Modes](#three-agent-modes)
- [Quick Start](#quick-start)
- [Built-in Tools](#built-in-tools)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Documentation & Community](#documentation--community)
- [License](#license)

---

## Introduction

LikeCodex is a production-grade AI coding assistant built with a **Rust + Python + TypeScript** multi-language architecture. Its core design philosophy is **separation of control and intelligence**:

- **Rust** handles HTTP bridging, SSE event broadcasting, sandboxed execution, code indexing, and the ACP protocol — ensuring safety and performance
- **Python** drives the agent loop, tool orchestration, LLM calls, context management, memory systems, and skill infrastructure — enabling rapid iteration on agent logic
- **TypeScript (Next.js)** delivers a modern, Cursor-inspired Web UI

The entire system is deeply optimized for **DeepSeek prefix caching** using a three-zone context model (Immutable Prefix + Append-Only Log + Volatile Scratch), making multi-turn tool loops fast and cost-effective.

### Why LikeCodex?

| Scenario | Traditional Approach | LikeCodex |
|----------|-------------------|-----------|
| Code understanding & refactoring | Manually browse files | Agent reads codebase, analyzes dependencies, executes refactoring |
| Bug fixing | Locate → Fix → Verify, multi-step manual work | One-sentence description, agent completes the full pipeline |
| Test writing | Write test cases file by file | Agent generates & runs tests after analyzing code |
| Tech research | Search docs → Write demo → Verify | Agent searches web, writes code, and validates in one go |
| Project maintenance | Remember all project details | Vector memory persists project knowledge across sessions |

---

## Key Features

### 🧠 Deep DeepSeek Integration

- Native support for DeepSeek V4 Flash / Pro dual models
- Three-zone context model maximizes prefix cache hit rate, reducing API costs
- Dual-model coordination: Pro model for planning & research, Flash model for execution
- Thinking mode, reasoning_effort control, and cache metrics tracking

### 🛡️ Multi-Layer Security

- **Three approval modes**: Ask (read-only) / Agent (auto-execute) / Manual (step-by-step)
- **Shell risk classification**: 40+ read-only commands auto-approved, 30+ dangerous patterns immediately denied
- **Docker sandbox**: High-risk commands execute in isolated containers with resource limits
- **Checkpoint snapshots**: Automatic file backups before write operations, one-click rollback
- **Policy rule engine**: Per-tool allow/ask/deny with glob, literal, and prefix matching

### 🔧 Rich Tool Ecosystem

40+ built-in professional tools covering filesystem, shell execution, code search, Git operations, web scraping, browser automation, vision recognition, database queries, code review, performance profiling, and more. Extensible via the MCP protocol.

### 🧩 Intelligent Agent Capabilities

- **Agent Loop**: LLM reasoning → Tool calls → Result feedback → Continue reasoning, up to 50 automated cycles
- **Parallel dispatch**: Read-only tools execute concurrently in batches for maximum efficiency
- **Smart planning**: Automatically determines whether planning is needed, generates multi-step structured plans
- **Sub-agent orchestration**: Delegate complex sub-tasks to parallel child agents
- **Skills system**: Markdown-based playbook skills, reusable and shareable
- **Evidence ledger**: Automatically tracks todo and step completion status

### 💾 Three-Tier Memory System

- **Working memory**: Short-term in-memory storage for current session
- **Episodic memory**: Cross-session conversation summaries persisted to ChromaDB
- **Semantic memory**: Long-term knowledge, never automatically cleared
- Supports sentence-transformers / OpenAI / TF-IDF embedding backends

### 🌐 Multi-Form Interaction

- **Terminal CLI/TUI**: Full-screen terminal interface powered by Ratatui
- **Web UI**: Modern Cursor-inspired interface built with Next.js 15
- **Desktop app**: Native Tauri v2 desktop shell
- **ACP protocol**: Standard Agent Client Protocol v1 for VS Code, Zed, and other editor integrations
- **IM integration**: Approval bridge via imbot for instant messaging workflows

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   Interfaces Layer                           │
│   CLI / TUI        Web UI :3000     Tauri Desktop    ACP    │
│  (Rust Ratatui)  (Next.js + React)   (Desktop)    (Editor) │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP / SSE / WebSocket
┌────────────────────────┴────────────────────────────────────┐
│              Control Plane (Rust :8080)                      │
│  ┌──────────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ HTTP Bridge  │ │Event Bus │ │Sandbox   │ │Code Index │  │
│  │ Session Proxy│ │SSE Broad │ │Gateway   │ │FileIndex  │  │
│  │EngineBridge  │ │EventBus  │ │Docker    │ │CodeGraph  │  │
│  └──────────────┘ └──────────┘ └──────────┘ └───────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP REST + SSE
┌────────────────────────┴────────────────────────────────────┐
│              Agent Engine (Python :9090)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │AgentLoop │ │ToolReg   │ │Context   │ │LLM Provider    │  │
│  │Main Loop │ │40+ Tools │ │Cache-First│ │DeepSeek/OpenAI │  │
│  │Guards    │ │Registry  │ │Compaction│ │MCP/Claude/etc  │  │
│  │Coordinator│ │MCP Ext   │ │Memory    │ │Local Models   │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │ LLM API Calls
┌────────────────────────┴────────────────────────────────────┐
│                   External Services                          │
│   DeepSeek V4 API     MCP Plugin Servers    Docker Sandbox  │
│   (Default LLM)       (Tool Extensions)    (Isolation)      │
└─────────────────────────────────────────────────────────────┘
```

### End-to-End Task Flow

Example: *"Add unit tests for `utils.py` and run them"* from the Web UI:

```
Browser           Rust Server :8080        Python Engine :9090        DeepSeek
  │                    │                        │                      │
  │ POST /tasks        │                        │                      │
  │───────────────────►│ POST /tasks (forward)   │                      │
  │                    │───────────────────────►│ AgentLoop.run()      │
  │                    │                        │─────────────────────►│
  │                    │                        │◄─────────────────────│ tool_calls
  │                    │                        │ read_file, edit_file │
  │                    │                        │ run_command          │
  │                    │◄── SSE stream ────────│                      │
  │                    │ map → EventBus         │                      │
  │ GET /events (SSE)  │                        │                      │
  │◄───────────────────│ stream_chunk           │                      │
  │                    │ tool_call_requested    │                      │
  │                    │ permission_requested   │                      │
  │                    │ task_completed         │                      │
```

---

## Three Agent Modes

LikeCodex provides three interaction modes, modeled after the Cursor Agent experience:

| Mode | Badge | Description | Use Case |
|------|-------|-------------|----------|
| **Ask** | 🟢 | Read-only mode. Agent only uses read tools to answer questions, never modifies files | Code understanding, architecture questions, general Q&A |
| **Agent** | 🔵 | Full-auto mode. Agent autonomously reads, writes, and executes commands with minimal intervention | Daily coding, bug fixing, refactoring |
| **Manual** | 🟠 | Step-by-step mode. Every write or command execution requires your approval | Critical code changes, unfamiliar projects |

> Modes can be switched at runtime without restarting the session.

---

## Quick Start

### Prerequisites

| Tool | Minimum Version | Notes |
|------|----------------|-------|
| Python | 3.11+ | Required for agent engine |
| uv / pip | Latest | Python package manager |
| Rust | 1.70+ | Required for CLI and server |
| Node.js | 20+ | Required for Web UI |
| Docker | Latest (optional) | Sandbox isolation |

### Quick Install (Python-only)

```bash
pip install likecodex

# First-time configuration
likecodex --setup

# Interactive chat mode
likecodex --chat

# One-shot task
likecodex "fix this bug"
```

### Full Install (Recommended)

```bash
# Clone the repository
git clone https://github.com/JasonBuildAI/likecodex.git
cd likecodex

# Install Python dependencies
uv sync --all-packages --extra dev

# Install Web UI dependencies
cd web && npm install --legacy-peer-deps && cd ..

# Build Rust components
cargo build --workspace

# First-time configuration
likecodex setup

# Start the full stack
likecodex start --web

# Or terminal-only TUI
likecodex code
```

### Windows Users

On Windows, install MSVC Build Tools first, then run:

```powershell
.\scripts\check-prerequisites.ps1
```

---

## Built-in Tools

LikeCodex ships with 40+ professional tools across the following categories:

| Category | Tools |
|----------|-------|
| **Filesystem** | `read_file`, `write_file`, `edit_file`, `multi_edit`, `glob`, `ls`, `move_file`, `search_files` |
| **Shell** | `run_command`, `bgjobs`, `bash_output`, `kill_shell`, `wait_job` |
| **Code Search** | `grep_files`, `codegraph_search`, `codegraph_related`, `code_index`, `code_search`, `find_symbol`, `semantic_search` |
| **LSP Semantics** | `lsp_definition`, `lsp_references`, `lsp_hover`, `lsp_diagnostics`, `lsp_code_action` |
| **Git** | `git_status`, `git_diff`, `git_log`, `git_branch`, `git_commit`, `git_push` |
| **GitHub** | `github_create_pr`, `github_review_pr`, `github_add_pr_comment`, `github_create_issue`, `github_list_prs`, `github_list_issues` |
| **Code Review** | `review_file`, `review_diff`, `check_dependencies` |
| **Refactoring** | `refactor_rename`, `refactor_extract`, `refactor_move_to_file` |
| **Testing** | `discover_tests`, `run_tests`, `analyze_failures`, `collect_coverage`, `coverage_summary` |
| **Web** | `web_search`, `web_fetch`, `net_ping`, `net_dns_lookup`, `net_traceroute`, `net_port_scan` |
| **Database** | `db_query`, `db_schema`, `db_explain`, `db_list_tables` |
| **Browser** | `browser_navigate`, `browser_click`, `browser_type`, `browser_screenshot`, etc. |
| **Vision** | `vision_analyze`, `vision_compare`, `vision_extract_text` |
| **Agent Meta** | `task` (sub-agent), `parallel_tasks`, `run_skill`, `todo_write`, `complete_step`, `ask` |
| **Memory** | `remember`, `forget`, `memory_search`, `history` |
| **Log Analysis** | `log_analyze`, `log_tail`, `log_grep`, `log_error_summary` |
| **API Testing** | `api_http_request`, `api_websocket_test` |
| **MCP Extensions** | `mcp__<server>__<tool>` (registered via external MCP servers) |

---

## Configuration

Configuration uses a layered merge strategy (lowest → highest priority):

```
Defaults → ~/.likecodex/config.toml → likecodex.toml → env vars → CLI flags
```

### User-level Config (`~/.likecodex/config.toml`)

```toml
[llm]
provider = "deepseek"
model = "deepseek-v4-flash"
api_key = "your-api-key"
base_url = "https://api.deepseek.com"

[approval]
mode = "auto"  # read-only | auto | full-access | sandbox-required

[agent]
enable_planner = false
token_mode = "full"  # full | economy
max_turns = 50

[server]
port = 8080
engine_url = "http://127.0.0.1:9090"

[sandbox]
enabled = true
allow_fallback = true
image = "likecodex/sandbox:latest"

[mcp]
enabled = false
startup = "lazy"  # lazy | eager

[deepseek]
thinking = false
reasoning_effort = "medium"
```

> Project-level overrides: Create a `likecodex.toml` in your repository root to override user-level settings.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `LIKECODEX_ENGINE_PORT` | Python engine port (default: 9090) |
| `LIKECODEX_WORKING_DIR` | Working directory path |

---

## Project Structure

```
likecodex/
├── crates/                           # Rust workspace (9 crates)
│   ├── likecodex-core/              # Shared types, config, event bus
│   ├── likecodex-cli/               # CLI entry, TUI, stack supervisor
│   ├── likecodex-server/            # Axum HTTP/SSE server + engine bridge
│   ├── likecodex-executor/          # Local command execution
│   ├── likecodex-sandbox/           # Docker/local sandbox isolation
│   ├── likecodex-indexer/           # File index + CodeGraph symbol graph
│   ├── likecodex-acp/               # Agent Client Protocol v1
│   ├── likecodex-desktop/           # Tauri desktop app shell
│   └── likecodex-ide-fs/            # IDE filesystem abstraction
├── packages/likecodex-engine/       # Python agent engine (brain)
│   └── likecodex_engine/
│       ├── agent/                   # AgentLoop, coordinator, guards
│       ├── tools/                   # 40+ built-in tool registry
│       ├── context/                 # Cache-first context + compaction
│       ├── llm/                     # LLM providers (DeepSeek/OpenAI/Claude/etc)
│       ├── permissions/             # Approval modes + policy engine
│       ├── memory/                  # Three-tier vector memory
│       ├── mcp/                     # MCP client + manager
│       ├── skills/                  # Skill system (Markdown playbooks)
│       ├── persistence/             # SQLite session persistence
│       ├── prompts/                 # System prompt templates
│       ├── hooks/                   # Hook system
│       ├── lsp/                     # LSP language server client
│       ├── composer/                # Composer multi-file editing
│       └── routes/                  # HTTP API routes
├── web/                             # Next.js 15 Web UI
│   └── src/
│       ├── components/              # React components
│       ├── hooks/                   # Custom hooks
│       ├── lib/                     # State management, API services, i18n
│       └── app/                     # Page entry points
├── docs/                            # English documentation
├── doc/                             # Chinese design documents
├── docker/                          # Docker build files
├── scripts/                         # Dev/install scripts
├── tests/                           # Python tests
├── benchmarks/                      # Performance benchmarks
└── services/                        # Additional services (imbot)
```

---

## Documentation & Community

| Resource | Description |
|----------|-------------|
| [README.zh-CN.md](README.zh-CN.md) | 中文文档 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architecture reference |
| [docs/API.md](docs/API.md) | HTTP API reference |
| [docs/USAGE.md](docs/USAGE.md) | Detailed usage guide |
| [docs/SPEC-CACHE.md](docs/SPEC-CACHE.md) | Cache-first context specification |
| [docs/SPEC-AGENT.md](docs/SPEC-AGENT.md) | Agent specification |
| [docs/ACP.md](docs/ACP.md) | Agent Client Protocol spec |
| [docs/EVENTS.md](docs/EVENTS.md) | SSE event schema |
| [docs/SECURITY.md](docs/SECURITY.md) | Security policy |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Project roadmap |
| [CHANGELOG.md](CHANGELOG.md) | Release changelog |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution guide |

---

## License

LikeCodex is open-sourced under the **MIT** license. See [LICENSE](LICENSE).

---

> Inspired by OpenAI Codex, Cursor, and the broader AI coding ecosystem.
