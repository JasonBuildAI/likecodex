<#
.SYNOPSIS
    LikeCodex Tauri 桌面版构建与启动脚本
.DESCRIPTION
    自动完成：环境检查 → API Key 配置 → Rust 构建 → Web UI 构建 → 启动 Tauri 桌面应用。
    需要先安装 WebView2 (Windows 10+ 已内置)。
#>

$ErrorActionPreference = "Stop"
# 自动解析项目根目录 (脚本在 scripts/ 下)
$PROJ = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Color { param($C) Write-Host $args[0] -ForegroundColor $C }
function Ok   { Color Green  "[✓] $args" }
function Warn { Color Yellow "[!] $args" }
function Info { Color Cyan   "[i] $args" }
function Step { Color Magenta "`n==> $args" }

# ── 1. 环境检查 ──
Step "检查环境依赖..."

$checks = @(
    @{Name="rustc";  Cmd="rustc --version";   Hint="安装 Rust: https://rustup.rs"}
    @{Name="cargo";  Cmd="cargo --version";   Hint="安装 Rust: https://rustup.rs"}
    @{Name="node";   Cmd="node --version";    Hint="安装 Node.js: https://nodejs.org"}
    @{Name="npm";    Cmd="npm --version";     Hint="安装 Node.js: https://nodejs.org"}
    @{Name="uv";     Cmd="uv --version";      Hint="安装 uv: https://docs.astral.sh/uv/"}
    @{Name="python"; Cmd="python --version";  Hint="安装 Python 3.11+"}
)

$allOk = $true
foreach ($c in $checks) {
    $result = & $c.Cmd 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) {
        Ok "$($c.Name) $($result.Trim())"
    } else {
        Warn "$($c.Name) 未找到 — $($c.Hint)"
        $allOk = $false
    }
}

if (-not $allOk) {
    Color Red "请安装缺失的依赖后重新运行。"
    exit 1
}

# ── 2. API Key ──
Step "检查 API Key..."
$configDir = "$env:USERPROFILE\.likecodex"
$configFile = "$configDir\config.toml"
$finalKey = $env:DEEPSEEK_API_KEY, $env:LIKECODEX_LLM_API_KEY | Where-Object { $_ } | Select-Object -First 1

if (Test-Path $configFile) {
    $content = Get-Content $configFile -Raw
    if ($content -match 'api_key\s*=\s*"([^"]+)"' -and -not $finalKey) {
        $finalKey = $matches[1]
    }
}

if (-not $finalKey) {
    $input = Read-Host "请输入你的 DeepSeek API Key"
    if ([string]::IsNullOrWhiteSpace($input)) { Color Red "需要 API Key 才能使用。"; exit 1 }
    $finalKey = $input.Trim()
}

# 写入配置
$configContent = @"
[llm]
provider = "deepseek"
model = "deepseek-v4-flash"
base_url = "https://api.deepseek.com"
api_key = "$finalKey"
[approval]
mode = "auto"
"@
if (-not (Test-Path $configDir)) { New-Item -ItemType Directory -Path $configDir -Force | Out-Null }
Set-Content -Path $configFile -Value $configContent
$env:LIKECODEX_LLM_API_KEY = $finalKey
$env:DEEPSEEK_API_KEY = $finalKey
Ok "API Key 已配置"

# ── 3. 安装 uv 依赖 ──
Step "安装 Python 依赖..."
Push-Location $PROJ
uv sync --all-packages 2>&1 | Out-Null
Pop-Location
Ok "Python 依赖就绪"

# ── 4. 构建 Rust 工作空间 (含 desktop crate) ──
Step "构建 Rust 工作空间..."
Push-Location $PROJ
$serverBin = "$PROJ\target\debug\likecodex-server.exe"
if (-not (Test-Path $serverBin)) {
    Info "编译 likecodex-server..."
    cargo build -p likecodex-server 2>&1
    if ($LASTEXITCODE -ne 0) { Color Red "构建失败"; exit 1 }
}
Pop-Location
Ok "Rust 构建完成"

# ── 5. 构建 Web UI 生产版本 (Tauri 需要静态导出) ──
Step "构建 Web UI 生产版本..."
Push-Location "$PROJ\web"
if (-not (Test-Path "node_modules")) {
    Info "安装 npm 依赖..."
    npm install 2>&1 | Out-Null
}
Info "执行 npm run build (静态导出)..."
npm run build 2>&1
if ($LASTEXITCODE -ne 0) { Color Red "Web UI 构建失败"; exit 1 }
Pop-Location
Ok "Web UI 构建完成"

# ── 6. 安装/检查 Tauri CLI ──
Step "检查 Tauri CLI..."
$tauriInstalled = $false
try {
    cargo tauri --version 2>&1 | Out-Null
    $tauriInstalled = $true
} catch {}

if (-not $tauriInstalled) {
    Info "正在安装 Tauri CLI (cargo install tauri-cli)..."
    Info "这可能需要几分钟..."
    cargo install tauri-cli --version "^2" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Color Red "Tauri CLI 安装失败。"
        Color Yellow "请手动安装: cargo install tauri-cli --version \"^2\""
        exit 1
    }
    Ok "Tauri CLI 安装完成"
} else {
    Ok "Tauri CLI 已安装"
}

# ── 7. 启动桌面应用 ──
Step "启动 LikeCodex 桌面版..."
Color Green "如首次启动，Tauri 会下载 WebView2 和编译 desktop crate，请耐心等待。"
Push-Location "$PROJ\crates\likecodex-desktop"
cargo tauri dev 2>&1
Pop-Location

Ok "桌面版已关闭"
