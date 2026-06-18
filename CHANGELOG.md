# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
