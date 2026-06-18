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
