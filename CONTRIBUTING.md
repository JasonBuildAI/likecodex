# Contributing to LikeCodex

Thank you for your interest in contributing to LikeCodex!

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Architecture Overview](#architecture-overview)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Commit Message Format](#commit-message-format)
- [Documentation](#documentation)
- [Reporting Issues](#reporting-issues)
- [Security](#security)

---

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

---

## Architecture Overview

LikeCodex uses a **Python-first layered architecture**:

```
┌─────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ CLI (Python) │  │ Web (TS) │  │ Desktop  │  │ ACP      │
└──────┬───────┘  └─────┬────┘  │ (Tauri)  │  │ (Rust)   │
       │                │       └────┬─────┘  └─────┬────┘
       └────────────────┴────────────┴──────────────┘
                        │
               ┌────────▼────────┐
               │ Rust Control    │  likecodex-server :8080
               │ Plane (Axum)    │  SSE + EventBus + Execution
               └────────┬────────┘
                        │
               ┌────────▼────────┐
               │ Python Agent    │  likecodex-engine :9090
               │ Engine (aiohttp)│  Loop + Tools + Context + Memory
               └────────┬────────┘
                        │
               ┌────────▼────────┐
               │ DeepSeek V4 API │  LLM inference
               └─────────────────┘
```

### Key Design Decisions

1. **Python-first**: The agent engine (brain) is Python, making it easy to iterate on agent logic
2. **Rust for safety**: The control plane, execution gateway, and sandbox are Rust for performance and security
3. **Cache-first**: Conversations structured for DeepSeek prefix caching
4. **SSE event bus**: One event stream powers CLI, TUI, Web, and ACP clients

### Project Layout

```
likecodex/
├── packages/likecodex-engine/   # Python agent engine (main codebase)
│   └── likecodex_engine/
│       ├── agent/               # Agent loop, guards, planner, coordinator
│       ├── tools/               # 40+ built-in tool implementations
│       ├── context/             # Cache-first context management
│       ├── llm/                 # LLM providers (DeepSeek, Mock)
│       ├── permissions/         # Approval modes and policy engine
│       ├── mcp/                 # MCP client integration
│       ├── memory/              # Vector memory
│       ├── persistence/         # SQLite session persistence
│       ├── skills/              # Skill system
│       ├── prompts/             # System prompts
│       └── cli.py              # CLI entry point
├── crates/                      # Rust workspace (8 crates)
│   ├── likecodex-cli/          # CLI and TUI
│   ├── likecodex-server/       # HTTP/SSE control plane
│   ├── likecodex-executor/     # Command execution
│   ├── likecodex-sandbox/      # Docker sandbox
│   └── likecodex-indexer/     # Code indexing
├── web/                         # Next.js Web UI
├── docs/                        # Documentation
└── tests/                       # Test suite
```

---

## Development Setup

### Prerequisites

| Tool | Version | Required For |
|------|---------|-------------|
| Python | 3.11+ | Agent engine development |
| uv | latest | Python package management |
| Rust | 1.70+ | CLI, server, and crates development |
| Node.js | 20+ | Web UI development |
| Docker | latest | Sandbox testing (optional) |

### Step 1: Clone and Set Up Python

```bash
git clone https://github.com/JasonBuildAI/likecodex.git
cd likecodex

# Create virtual environment and install dependencies
uv sync --all-packages --extra dev
```

### Step 2: Set Up Environment

```bash
cp .env.example .env
# Edit .env with your DeepSeek API key
```

### Step 3: Install Pre-commit Hooks (optional)

```bash
# Copy the example hooks config
cp .likecodex/hooks.toml.example .likecodex/hooks.toml
```

### Step 4: Verify Setup

```bash
# Run the doctor
uv run likecodex --doctor

# Run tests
uv run pytest packages/likecodex-engine/tests -v -x --timeout=60
```

---

## Development Workflow

### Python Engine Development

The core agent engine is in `packages/likecodex-engine/`. Most feature work happens here.

```bash
# Run the engine directly
uv run python -m likecodex_engine.server

# In another terminal, test with CLI
uv run likecodex --chat

# Use mock LLM for faster iteration
$env:LIKECODEX_LLM_PROVIDER = "mock"
$env:LIKECODEX_LLM_MODEL = "mock"
```

### Adding a New Tool

1. Create a tool file in `packages/likecodex-engine/likecodex_engine/tools/`
2. Register the tool in `tools/registry.py`
3. Add tests in `packages/likecodex-engine/tests/`
4. Update the tool schema documentation

### Adding a New API Endpoint

1. Create or modify a route file in `packages/likecodex-engine/likecodex_engine/routes/`
2. Register the route in the server app factory
3. Add tests in `tests/` directory
4. Update `docs/API.md`

### Rust Crate Development

```bash
# Build all crates
cargo build --workspace

# Run Rust tests
cargo test --workspace

# Check formatting
cargo fmt -- --check

# Run clippy
cargo clippy --workspace --all-targets -- -D warnings
```

### Web UI Development

```bash
cd web
npm install --legacy-peer-deps
npm run dev
```

---

## Code Style Guidelines

### Python

- **Line length**: 120 characters
- **Formatter**: Ruff (`uv run ruff format`)
- **Linter**: Ruff (`uv run ruff check`)
- **Type checker**: mypy (`uv run mypy`)
- **Target**: Python 3.11+
- **Imports**: Use `from __future__ import annotations` in all files
- **Docstrings**: Google-style docstrings
- **Type hints**: Required for all function signatures

### Rust

- **Formatter**: `cargo fmt`
- **Linter**: `cargo clippy` (deny warnings)
- **Naming**: Snake case for functions/variables, PascalCase for types
- **Error handling**: Use `anyhow` for CLI, custom error types for libraries

### TypeScript / Web

- **Framework**: Next.js 15 + React 19
- **Styling**: Tailwind CSS
- **State management**: Zustand 5
- **Type safety**: Strict TypeScript

### General

- Write clear, self-documenting code
- Keep functions small and focused
- Add comments for complex logic
- Follow the principle of least surprise

---

## Testing

### Running Tests

```bash
# All Python tests
uv run pytest packages/likecodex-engine/tests tests -v -x --timeout=60

# Fast tests only (no Rust)
uv run pytest packages/likecodex-engine/tests -v -x

# Specific test file
uv run pytest tests/test_agent_guards.py -v

# With coverage
uv run pytest --cov=likecodex_engine --cov-report=term-missing
```

### Test Categories

| Marker | Description |
|--------|-------------|
| `(none)` | Unit tests (fast, no external dependencies) |
| `pytest.mark.asyncio` | Async engine tests |
| `pytest.mark.integration` | Full-stack tests requiring engine and Rust server |

### Writing Tests

- Place engine unit tests in `packages/likecodex-engine/tests/`
- Place integration/e2e tests in `tests/` directory
- Use the `mock` LLM provider for tests that don't need real API calls
- Use `tempfile.TemporaryDirectory` for file operation tests

### E2E Test Setup

Full-stack tests require Rust server and Python engine running together:

```bash
# Set mock provider
$env:LIKECODEX_LLM_PROVIDER = "mock"
$env:LIKECODEX_LLM_MODEL = "mock"

# Run engine + server E2E tests
uv run pytest tests/e2e/test_full_stack.py -v -m integration --timeout=120
```

---

## Pull Request Process

1. **Fork the repository** and create a feature branch from `main`
2. **Make your changes** following the code style guidelines
3. **Add or update tests** for behavior changes
4. **Run tests** to ensure nothing is broken
5. **Update documentation** when APIs, config, or ports change
6. **Create a pull request** with a clear description of the changes

### PR Checklist

- [ ] Code follows style guidelines
- [ ] Tests pass (`uv run pytest ...`)
- [ ] New tests added for new functionality
- [ ] Documentation updated (if applicable)
- [ ] Commit messages follow conventional commits
- [ ] No unnecessary changes (formatting, whitespace)

### Review Process

1. At least one maintainer review is required
2. Address review comments promptly
3. Keep PRs focused and well-scoped
4. Larger changes should be discussed in an issue first

---

## Commit Message Format

We use conventional commits:

```
type(scope): short description

Optional longer explanation explaining the change.
```

### Types

| Type | Usage |
|------|-------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation |
| `test` | Tests |
| `refactor` | Code restructuring |
| `chore` | Build/config changes |
| `style` | Formatting |

### Examples

```
feat(engine): add MCP tool loader
fix(web): parse Rust SSE event payload
docs(readme): add deployment section
test(agent): add planner isolation tests
refactor(permissions): simplify policy evaluation
```

---

## Documentation

- All new features should include documentation
- API changes require updates to `docs/API.md`
- Architecture changes should be reflected in `docs/ARCHITECTURE.md`
- User-facing features need updates to `README.md` or `docs/USER_GUIDE.md`

---

## Reporting Issues

Please include:
- OS version (e.g., Windows 11, Ubuntu 22.04)
- Tool versions: `python --version`, `rustc --version`, `node --version`
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (redact API keys and secrets)

---

## Security

Do not open public issues for security vulnerabilities. Please report security concerns privately by contacting the maintainers.

See [SECURITY.md](SECURITY.md) for the full security policy.
# Contributing to LikeCodex

Thank you for your interest in contributing to LikeCodex!

## Getting Started

1. Fork the repository and clone it locally.
2. Install prerequisites: Rust, Python 3.11+, uv, Node.js 20+, Docker (optional).
3. Copy `.env.example` to `.env` and configure your LLM provider.
4. Start the dev stack:

```bash
./scripts/dev.sh
# Windows: .\scripts\dev.ps1
```

## Development Workflow

```bash
# Rust
cargo fmt --all
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace

# Python
uv sync --all-packages
uv run ruff check packages/likecodex-engine tests
uv run pytest packages/likecodex-engine/tests tests -v

# Web
cd web && npm install --legacy-peer-deps
npm run lint && npm run type-check && npm run test && npm run build
```

## Pull Request Guidelines

- Keep changes focused and well-scoped.
- Add or update tests for behavior changes.
- Update docs when APIs, config, or ports change.
- Follow existing code style in each language.
- Write clear commit messages (see below).

## Commit Message Format

We prefer conventional commits:

```
type(scope): short description

Optional longer explanation.
```

Examples:

- `feat(engine): add MCP tool loader`
- `fix(web): parse Rust SSE event payload`
- `docs(readme): add deployment section`

## Reporting Issues

Please include:

- OS and versions (Rust, Python, Node)
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (redact API keys)

## Security

Do not open public issues for security vulnerabilities. See [SECURITY.md](SECURITY.md).
