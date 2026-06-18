# Initialize LikeCodex git history with ~100 logical commits.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)

git rev-parse --verify HEAD 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Error "Repository already has commits. Aborting."
    exit 1
}
$ErrorActionPreference = "Stop"

function Commit-Files {
    param([string]$Message, [string[]]$Files)
    git add @Files
    git commit -m $Message
    if ($LASTEXITCODE -ne 0) { throw "Commit failed: $Message" }
}

$commits = @(
    @("chore: add gitignore for Rust, Python, and Node artifacts", @(".gitignore")),
    @("docs: add MIT license", @("LICENSE")),
    @("docs: add contributor code of conduct", @("CODE_OF_CONDUCT.md")),
    @("docs: add security policy", @("SECURITY.md")),
    @("docs: add changelog", @("CHANGELOG.md")),
    @("docs: add contributing guide", @("CONTRIBUTING.md")),
    @("chore: add environment variable template", @(".env.example")),
    @("build: add Rust workspace manifest", @("Cargo.toml")),
    @("build: add Python workspace manifest", @("pyproject.toml")),
    @("build: lock Python dependencies with uv", @("uv.lock")),
    @("docs: add English README with quick start and architecture", @("README.md")),
    @("docs: add Chinese README", @("README.zh-CN.md")),
    @("docs: add architecture overview", @("docs/ARCHITECTURE.md")),
    @("docs: add HTTP API reference", @("docs/API.md")),
    @("docs: document SSE event schema", @("docs/EVENTS.md")),
    @("docs: add usage guide", @("docs/USAGE.md")),
    @("ci: add bug report issue template", @(".github/ISSUE_TEMPLATE/bug_report.yml")),
    @("ci: add feature request issue template", @(".github/ISSUE_TEMPLATE/feature_request.yml")),
    @("ci: add pull request template", @(".github/pull_request_template.md")),
    @("ci: add GitHub Actions workflow", @(".github/workflows/ci.yml")),
    @("feat(core): add crate manifest", @("crates/likecodex-core/Cargo.toml")),
    @("feat(core): add configuration loading and redaction", @("crates/likecodex-core/src/config.rs")),
    @("feat(core): add event bus and event types", @("crates/likecodex-core/src/events.rs")),
    @("feat(core): add shared domain types and unit tests", @("crates/likecodex-core/src/lib.rs")),
    @("feat(executor): add crate manifest", @("crates/likecodex-executor/Cargo.toml")),
    @("feat(executor): add local command executor", @("crates/likecodex-executor/src/lib.rs")),
    @("feat(sandbox): add crate manifest", @("crates/likecodex-sandbox/Cargo.toml")),
    @("feat(sandbox): add sandbox policy types", @("crates/likecodex-sandbox/src/policy.rs")),
    @("feat(sandbox): add local fallback executor", @("crates/likecodex-sandbox/src/fallback.rs")),
    @("feat(sandbox): add Docker executor with hardening flags", @("crates/likecodex-sandbox/src/docker.rs")),
    @("feat(sandbox): unify sandbox executor with fallback control", @("crates/likecodex-sandbox/src/lib.rs")),
    @("build(docker): add sandbox Dockerfile", @("docker/sandbox/Dockerfile")),
    @("feat(indexer): add crate manifest", @("crates/likecodex-indexer/Cargo.toml")),
    @("feat(indexer): add file index and name search", @("crates/likecodex-indexer/src/lib.rs")),
    @("feat(server): add crate manifest", @("crates/likecodex-server/Cargo.toml")),
    @("feat(server): add Python engine HTTP bridge", @("crates/likecodex-server/src/engine_bridge.rs")),
    @("feat(server): map engine outputs to structured events", @("crates/likecodex-server/src/event_mapping.rs")),
    @("feat(server): add Axum API with auth, CORS, and index route", @("crates/likecodex-server/src/main.rs")),
    @("build(docker): add server Dockerfile", @("docker/server/Dockerfile")),
    @("feat(cli): add crate manifest", @("crates/likecodex-cli/Cargo.toml")),
    @("feat(cli): add terminal permission helpers", @("crates/likecodex-cli/src/interaction.rs")),
    @("feat(cli): add CLI with serve, approval, and chat modes", @("crates/likecodex-cli/src/main.rs")),
    @("feat(cli): add Ratatui interactive interface", @("crates/likecodex-cli/src/tui.rs")),
    @("feat(engine): add package manifest", @("packages/likecodex-engine/pyproject.toml")),
    @("docs(engine): add package README", @("packages/likecodex-engine/README.md")),
    @("feat(engine): export public API", @("packages/likecodex-engine/likecodex_engine/__init__.py")),
    @("feat(engine): add system prompt template", @("packages/likecodex-engine/likecodex_engine/prompts/system.md")),
    @("feat(llm): add provider base types", @("packages/likecodex-engine/likecodex_engine/llm/base.py")),
    @("feat(llm): add mock provider for tests", @("packages/likecodex-engine/likecodex_engine/llm/mock.py")),
    @("feat(llm): add OpenAI provider", @("packages/likecodex-engine/likecodex_engine/llm/openai.py")),
    @("feat(llm): add Anthropic provider", @("packages/likecodex-engine/likecodex_engine/llm/anthropic.py")),
    @("feat(llm): add provider factory", @("packages/likecodex-engine/likecodex_engine/llm/factory.py")),
    @("feat(context): add context compaction", @("packages/likecodex-engine/likecodex_engine/context/compaction.py")),
    @("feat(context): add conversation manager", @("packages/likecodex-engine/likecodex_engine/context/manager.py")),
    @("feat(permissions): add risk classifier", @("packages/likecodex-engine/likecodex_engine/permissions/classifier.py")),
    @("feat(permissions): add approval evaluator", @("packages/likecodex-engine/likecodex_engine/permissions/evaluator.py")),
    @("feat(tools): add path confinement utilities", @("packages/likecodex-engine/likecodex_engine/tools/path_utils.py")),
    @("feat(tools): add filesystem tools with size limits", @("packages/likecodex-engine/likecodex_engine/tools/filesystem.py")),
    @("feat(tools): add hardened shell execution", @("packages/likecodex-engine/likecodex_engine/tools/shell.py")),
    @("feat(tools): add git tools with argument vectors", @("packages/likecodex-engine/likecodex_engine/tools/git.py")),
    @("feat(tools): add code search and indexer integration", @("packages/likecodex-engine/likecodex_engine/tools/code_search.py")),
    @("feat(tools): add static code review helpers", @("packages/likecodex-engine/likecodex_engine/tools/code_review.py")),
    @("feat(tools): add tool registry and dispatch", @("packages/likecodex-engine/likecodex_engine/tools/registry.py")),
    @("feat(agent): add task planner", @("packages/likecodex-engine/likecodex_engine/agent/planner.py")),
    @("feat(agent): add sub-agent orchestrator", @("packages/likecodex-engine/likecodex_engine/agent/subagent.py")),
    @("feat(agent): add agent loop with permissions and planning", @("packages/likecodex-engine/likecodex_engine/agent/loop.py")),
    @("feat(memory): export memory module", @("packages/likecodex-engine/likecodex_engine/memory/__init__.py")),
    @("feat(memory): add vector memory with chromadb fallback", @("packages/likecodex-engine/likecodex_engine/memory/vector.py")),
    @("feat(mcp): export MCP module", @("packages/likecodex-engine/likecodex_engine/mcp/__init__.py")),
    @("feat(mcp): add stdio MCP client", @("packages/likecodex-engine/likecodex_engine/mcp/client.py")),
    @("feat(mcp): add MCP server configuration", @("packages/likecodex-engine/likecodex_engine/mcp/servers.json")),
    @("feat(mcp): add MCP tool loader", @("packages/likecodex-engine/likecodex_engine/mcp/loader.py")),
    @("feat(persistence): export persistence module", @("packages/likecodex-engine/likecodex_engine/persistence/__init__.py")),
    @("feat(persistence): add SQLite session store", @("packages/likecodex-engine/likecodex_engine/persistence/session.py")),
    @("feat(engine): add HTTP bridge server", @("packages/likecodex-engine/likecodex_engine/server.py")),
    @("test(engine): add agent loop tests", @("packages/likecodex-engine/tests/test_agent_loop.py")),
    @("test(engine): add tool tests", @("packages/likecodex-engine/tests/test_tools.py")),
    @("test(engine): add server tests", @("packages/likecodex-engine/tests/test_server.py")),
    @("test: add security tests for path and git hardening", @("tests/test_security.py")),
    @("test: add permission flow tests", @("tests/test_permissions.py")),
    @("test: add vector memory tests", @("tests/test_memory.py")),
    @("test: add planner tests", @("tests/test_planner.py")),
    @("test: add sub-agent tests", @("tests/test_subagent.py")),
    @("test: add MCP loader tests", @("tests/test_mcp.py")),
    @("test(e2e): add API contract tests", @("tests/e2e/test_api_contract.py")),
    @("test(e2e): add simple task smoke tests", @("tests/e2e/test_simple_task.py")),
    @("feat(web): add Next.js package manifest", @("web/package.json")),
    @("feat(web): lock npm dependencies", @("web/package-lock.json")),
    @("feat(web): add TypeScript config", @("web/tsconfig.json")),
    @("feat(web): add Next.js config with API proxy", @("web/next.config.js")),
    @("feat(web): add Tailwind and PostCSS config", @("web/tailwind.config.js", "web/postcss.config.js")),
    @("feat(web): add Next.js type declarations", @("web/next-env.d.ts")),
    @("feat(web): add global styles", @("web/src/app/globals.css")),
    @("feat(web): add root layout", @("web/src/app/layout.tsx")),
    @("feat(web): add Zustand store", @("web/src/lib/store.ts")),
    @("feat(web): add API client with SSE event parsing", @("web/src/lib/api.ts")),
    @("test(web): add API parsing unit tests", @("web/src/lib/api.test.ts")),
    @("feat(web): add chat message component", @("web/src/components/Chat.tsx")),
    @("feat(web): add task timeline sidebar", @("web/src/components/TaskTimeline.tsx")),
    @("feat(web): add diff viewer panel", @("web/src/components/DiffViewer.tsx")),
    @("feat(web): add permission approval modal", @("web/src/components/PermissionModal.tsx")),
    @("feat(web): add tool call card component", @("web/src/components/ToolCallCard.tsx")),
    @("feat(web): add three-column main page", @("web/src/app/page.tsx")),
    @("chore: add Unix development launcher", @("scripts/dev.sh")),
    @("chore: add Windows development launcher", @("scripts/dev.ps1")),
    @("chore: add commit history bootstrap scripts", @("scripts/commit-history.sh", "scripts/commit-history.ps1")),
    @("chore: add Docker Compose stack", @("docker-compose.yml"))
)

$i = 0
foreach ($entry in $commits) {
    $i++
    $msg = $entry[0]
    $files = $entry[1]
    Write-Host "[$i/$($commits.Count)] $msg"
    Commit-Files -Message $msg -Files $files
}

$total = git rev-list --count HEAD
Write-Host ""
Write-Host "Done. Total commits: $total"
