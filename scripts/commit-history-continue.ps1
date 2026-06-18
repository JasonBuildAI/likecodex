# Continue commit history from step 78 (after partial run).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Commit-Files {
    param([string]$Message, [string[]]$Files)
    git add @Files
    git commit -m $Message
    if ($LASTEXITCODE -ne 0) { throw "Commit failed: $Message" }
}

Commit-Files "fix: scope root test_server ignore pattern" @(".gitignore")

$remaining = @(
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
    @("chore: add commit history bootstrap scripts", @("scripts/commit-history.sh", "scripts/commit-history.ps1", "scripts/commit-history-continue.ps1")),
    @("chore: add Docker Compose stack", @("docker-compose.yml"))
)

$i = 0
foreach ($entry in $remaining) {
    $i++
    Write-Host "[$i/$($remaining.Count)] $($entry[0])"
    Commit-Files -Message $entry[0] -Files $entry[1]
}

# Add any optional package marker files if present
$optional = @(
    @("chore(engine): add py.typed marker", @("packages/likecodex-engine/likecodex_engine/py.typed")),
    @("chore(engine): add agent package init", @("packages/likecodex-engine/likecodex_engine/agent/__init__.py")),
    @("chore(engine): add context package init", @("packages/likecodex-engine/likecodex_engine/context/__init__.py")),
    @("chore(engine): add llm package init", @("packages/likecodex-engine/likecodex_engine/llm/__init__.py")),
    @("chore(engine): add tools package init", @("packages/likecodex-engine/likecodex_engine/tools/__init__.py")),
    @("chore(engine): add tests package init", @("packages/likecodex-engine/tests/__init__.py"))
)
foreach ($entry in $optional) {
    $exists = $true
    foreach ($f in $entry[1]) { if (-not (Test-Path $f)) { $exists = $false } }
    if ($exists) { Commit-Files -Message $entry[0] -Files $entry[1] }
}

Write-Host "Total commits: $(git rev-list --count HEAD)"
