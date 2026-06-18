# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
