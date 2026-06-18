#!/usr/bin/env bash
# Initialize LikeCodex git history with ~100 logical commits.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -n "$(git rev-parse --verify HEAD 2>/dev/null || true)" ]; then
  echo "Repository already has commits. Aborting."
  exit 1
fi

c() {
  local msg="$1"
  shift
  git add "$@"
  git commit -m "$msg"
}

# ── Phase 1: Repository foundation ──────────────────────────────────
c "chore: add gitignore for Rust, Python, and Node artifacts" .gitignore
c "docs: add MIT license" LICENSE
c "docs: add contributor code of conduct" CODE_OF_CONDUCT.md
c "docs: add security policy" SECURITY.md
c "docs: add changelog" CHANGELOG.md
c "docs: add contributing guide" CONTRIBUTING.md
c "chore: add environment variable template" .env.example

# ── Phase 2: Workspace manifests ────────────────────────────────────
c "build: add Rust workspace manifest" Cargo.toml
c "build: add Python workspace manifest" pyproject.toml
c "build: lock Python dependencies with uv" uv.lock

# ── Phase 3: Documentation ─────────────────────────────────────────
c "docs: add English README with quick start and architecture" README.md
c "docs: add Chinese README" README.zh-CN.md
c "docs: add architecture overview" docs/ARCHITECTURE.md
c "docs: add HTTP API reference" docs/API.md
c "docs: document SSE event schema" docs/EVENTS.md
c "docs: add usage guide" docs/USAGE.md

# ── Phase 4: GitHub templates ───────────────────────────────────────
c "ci: add bug report issue template" .github/ISSUE_TEMPLATE/bug_report.yml
c "ci: add feature request issue template" .github/ISSUE_TEMPLATE/feature_request.yml
c "ci: add pull request template" .github/pull_request_template.md
c "ci: add GitHub Actions workflow" .github/workflows/ci.yml

# ── Phase 5: likecodex-core ─────────────────────────────────────────
c "feat(core): add crate manifest" crates/likecodex-core/Cargo.toml
c "feat(core): add configuration loading and redaction" crates/likecodex-core/src/config.rs
c "feat(core): add event bus and event types" crates/likecodex-core/src/events.rs
c "feat(core): add shared domain types and unit tests" crates/likecodex-core/src/lib.rs

# ── Phase 6: likecodex-executor ─────────────────────────────────────
c "feat(executor): add crate manifest" crates/likecodex-executor/Cargo.toml
c "feat(executor): add local command executor" crates/likecodex-executor/src/lib.rs

# ── Phase 7: likecodex-sandbox ────────────────────────────────────
c "feat(sandbox): add crate manifest" crates/likecodex-sandbox/Cargo.toml
c "feat(sandbox): add sandbox policy types" crates/likecodex-sandbox/src/policy.rs
c "feat(sandbox): add local fallback executor" crates/likecodex-sandbox/src/fallback.rs
c "feat(sandbox): add Docker executor with hardening flags" crates/likecodex-sandbox/src/docker.rs
c "feat(sandbox): unify sandbox executor with fallback control" crates/likecodex-sandbox/src/lib.rs
c "build(docker): add sandbox Dockerfile" docker/sandbox/Dockerfile

# ── Phase 8: likecodex-indexer ──────────────────────────────────────
c "feat(indexer): add crate manifest" crates/likecodex-indexer/Cargo.toml
c "feat(indexer): add file index and name search" crates/likecodex-indexer/src/lib.rs

# ── Phase 9: likecodex-server ───────────────────────────────────────
c "feat(server): add crate manifest" crates/likecodex-server/Cargo.toml
c "feat(server): add Python engine HTTP bridge" crates/likecodex-server/src/engine_bridge.rs
c "feat(server): map engine outputs to structured events" crates/likecodex-server/src/event_mapping.rs
c "feat(server): add Axum API with auth, CORS, and index route" crates/likecodex-server/src/main.rs
c "build(docker): add server Dockerfile" docker/server/Dockerfile

# ── Phase 10: likecodex-cli ─────────────────────────────────────────
c "feat(cli): add crate manifest" crates/likecodex-cli/Cargo.toml
c "feat(cli): add terminal permission helpers" crates/likecodex-cli/src/interaction.rs
c "feat(cli): add CLI with serve, approval, and chat modes" crates/likecodex-cli/src/main.rs
c "feat(cli): add Ratatui interactive interface" crates/likecodex-cli/src/tui.rs

# ── Phase 11: Python engine package ─────────────────────────────────
c "feat(engine): add package manifest" packages/likecodex-engine/pyproject.toml
c "docs(engine): add package README" packages/likecodex-engine/README.md
c "feat(engine): export public API" packages/likecodex-engine/likecodex_engine/__init__.py
c "feat(engine): add system prompt template" packages/likecodex-engine/likecodex_engine/prompts/system.md

# ── Phase 12: LLM providers ─────────────────────────────────────────
c "feat(llm): add provider base types" packages/likecodex-engine/likecodex_engine/llm/base.py
c "feat(llm): add mock provider for tests" packages/likecodex-engine/likecodex_engine/llm/mock.py
c "feat(llm): add OpenAI provider" packages/likecodex-engine/likecodex_engine/llm/openai.py
c "feat(llm): add Anthropic provider" packages/likecodex-engine/likecodex_engine/llm/anthropic.py
c "feat(llm): add provider factory" packages/likecodex-engine/likecodex_engine/llm/factory.py

# ── Phase 13: Context management ────────────────────────────────────
c "feat(context): add context compaction" packages/likecodex-engine/likecodex_engine/context/compaction.py
c "feat(context): add conversation manager" packages/likecodex-engine/likecodex_engine/context/manager.py

# ── Phase 14: Permissions ───────────────────────────────────────────
c "feat(permissions): add risk classifier" packages/likecodex-engine/likecodex_engine/permissions/classifier.py
c "feat(permissions): add approval evaluator" packages/likecodex-engine/likecodex_engine/permissions/evaluator.py

# ── Phase 15: Tools ─────────────────────────────────────────────────
c "feat(tools): add path confinement utilities" packages/likecodex-engine/likecodex_engine/tools/path_utils.py
c "feat(tools): add filesystem tools with size limits" packages/likecodex-engine/likecodex_engine/tools/filesystem.py
c "feat(tools): add hardened shell execution" packages/likecodex-engine/likecodex_engine/tools/shell.py
c "feat(tools): add git tools with argument vectors" packages/likecodex-engine/likecodex_engine/tools/git.py
c "feat(tools): add code search and indexer integration" packages/likecodex-engine/likecodex_engine/tools/code_search.py
c "feat(tools): add static code review helpers" packages/likecodex-engine/likecodex_engine/tools/code_review.py
c "feat(tools): add tool registry and dispatch" packages/likecodex-engine/likecodex_engine/tools/registry.py

# ── Phase 16: Agent ─────────────────────────────────────────────────
c "feat(agent): add task planner" packages/likecodex-engine/likecodex_engine/agent/planner.py
c "feat(agent): add sub-agent orchestrator" packages/likecodex-engine/likecodex_engine/agent/subagent.py
c "feat(agent): add agent loop with permissions and planning" packages/likecodex-engine/likecodex_engine/agent/loop.py

# ── Phase 17: Memory, MCP, persistence ──────────────────────────────
c "feat(memory): export memory module" packages/likecodex-engine/likecodex_engine/memory/__init__.py
c "feat(memory): add vector memory with chromadb fallback" packages/likecodex-engine/likecodex_engine/memory/vector.py
c "feat(mcp): export MCP module" packages/likecodex-engine/likecodex_engine/mcp/__init__.py
c "feat(mcp): add stdio MCP client" packages/likecodex-engine/likecodex_engine/mcp/client.py
c "feat(mcp): add MCP server configuration" packages/likecodex-engine/likecodex_engine/mcp/servers.json
c "feat(mcp): add MCP tool loader" packages/likecodex-engine/likecodex_engine/mcp/loader.py
c "feat(persistence): export persistence module" packages/likecodex-engine/likecodex_engine/persistence/__init__.py
c "feat(persistence): add SQLite session store" packages/likecodex-engine/likecodex_engine/persistence/session.py
c "feat(engine): add HTTP bridge server" packages/likecodex-engine/likecodex_engine/server.py

# ── Phase 18: Python tests ──────────────────────────────────────────
c "test(engine): add agent loop tests" packages/likecodex-engine/tests/test_agent_loop.py
c "test(engine): add tool tests" packages/likecodex-engine/tests/test_tools.py
c "test(engine): add server tests" packages/likecodex-engine/tests/test_server.py

# ── Phase 19: Integration tests ─────────────────────────────────────
c "test: add security tests for path and git hardening" tests/test_security.py
c "test: add permission flow tests" tests/test_permissions.py
c "test: add vector memory tests" tests/test_memory.py
c "test: add planner tests" tests/test_planner.py
c "test: add sub-agent tests" tests/test_subagent.py
c "test: add MCP loader tests" tests/test_mcp.py
c "test(e2e): add API contract tests" tests/e2e/test_api_contract.py
c "test(e2e): add simple task smoke tests" tests/e2e/test_simple_task.py

# ── Phase 20: Web frontend ──────────────────────────────────────────
c "feat(web): add Next.js package manifest" web/package.json
c "feat(web): lock npm dependencies" web/package-lock.json
c "feat(web): add TypeScript config" web/tsconfig.json
c "feat(web): add Next.js config with API proxy" web/next.config.js
c "feat(web): add Tailwind and PostCSS config" web/tailwind.config.js web/postcss.config.js
c "feat(web): add Next.js type declarations" web/next-env.d.ts
c "feat(web): add global styles" web/src/app/globals.css
c "feat(web): add root layout" web/src/app/layout.tsx
c "feat(web): add Zustand store" web/src/lib/store.ts
c "feat(web): add API client with SSE event parsing" web/src/lib/api.ts
c "test(web): add API parsing unit tests" web/src/lib/api.test.ts
c "feat(web): add chat message component" web/src/components/Chat.tsx
c "feat(web): add task timeline sidebar" web/src/components/TaskTimeline.tsx
c "feat(web): add diff viewer panel" web/src/components/DiffViewer.tsx
c "feat(web): add permission approval modal" web/src/components/PermissionModal.tsx
c "feat(web): add tool call card component" web/src/components/ToolCallCard.tsx
c "feat(web): add three-column main page" web/src/app/page.tsx

# ── Phase 21: DevOps ────────────────────────────────────────────────
c "chore: add Unix development launcher" scripts/dev.sh
c "chore: add Windows development launcher" scripts/dev.ps1
c "chore: add Docker Compose stack" docker-compose.yml

echo ""
echo "Done. Total commits: $(git rev-list --count HEAD)"
