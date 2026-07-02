<#
.SYNOPSIS
    LikeCodex 一键启动脚本 — 构建并启动完整服务栈 (引擎 + API + Web UI)
.DESCRIPTION
    自动完成：环境检查 → API Key 配置 → Rust 构建 → Python 依赖安装 → 服务启动 → 打开浏览器。
    按 Ctrl+C 优雅关闭所有服务。
.PARAMETER Mode
    启动模式：
      lite - 极简模式 (默认): 仅启动 Python 引擎 + 内置 Lite UI (无需 Rust 编译)
      full - 完整模式: 引擎 + Rust API + Next.js Web UI
.PARAMETER SkipBuild
    跳过 Rust 构建 (已构建过时使用，加快启动)
.PARAMETER Port
    Web UI 端口 (默认 3000)
#>

param(
    [ValidateSet("full", "lite")]
    [string]$Mode = "lite",
    [switch]$SkipBuild,
    [int]$Port = 3000
)

$ErrorActionPreference = "Stop"
# 自动解析项目根目录 (脚本在 scripts/ 下)
$PROJ = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

# ── 颜色辅助 ──
function Color { param($C) Write-Host $args[0] -ForegroundColor $C }
function Ok   { Color Green  "[✓] $args" }
function Warn { Color Yellow "[!] $args" }
function Info { Color Cyan   "[i] $args" }
function Step { Color Magenta "`n==> $args" }

# ── 全局错误处理 ──
trap {
    Color Red "`n[错误] $($_.Exception.Message)"
    Color Yellow "脚本异常终止。按 Enter 键退出..."
    $null = Read-Host
    exit 1
}

# ── 检查管理员权限 ──
function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

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
    Color Yellow "按 Enter 键退出..."
    $null = Read-Host
    exit 1
}

# ── 2. API Key 配置 ──
Step "检查 API Key 配置..."

$configDir = "$env:USERPROFILE\.likecodex"
$configFile = "$configDir\config.toml"
$envKey = $env:DEEPSEEK_API_KEY
$envKey2 = $env:LIKECODEX_LLM_API_KEY

# 从已有配置文件读取
$existingKey = $null
if (Test-Path $configFile) {
    $content = Get-Content $configFile -Raw
    if ($content -match 'api_key\s*=\s*"([^"]+)"') {
        $existingKey = $matches[1]
    }
}

$finalKey = $envKey2, $envKey, $existingKey | Where-Object { $_ -ne $null -and $_ -ne "" } | Select-Object -First 1

if (-not $finalKey) {
    Warn "未检测到 DeepSeek API Key。"
    $input = Read-Host "请输入你的 DeepSeek API Key (输入后回车，留空则退出)"
    if ([string]::IsNullOrWhiteSpace($input)) {
        Color Red "未提供 API Key，退出。"
        Color Yellow "获取 API Key: https://platform.deepseek.com/api_keys"
        Color Yellow "按 Enter 键退出..."
        $null = Read-Host
        exit 1
    }
    $finalKey = $input.Trim()
}

# 写入配置文件
$configContent = @"
[llm]
provider = "deepseek"
model = "deepseek-v4-flash"
base_url = "https://api.deepseek.com"
api_key = "$finalKey"

[approval]
mode = "auto"

[agent]
enable_planner = false
token_mode = "full"
"@

if (-not (Test-Path $configDir)) {
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
}
Set-Content -Path $configFile -Value $configContent
$env:LIKECODEX_LLM_API_KEY = $finalKey
$env:DEEPSEEK_API_KEY = $finalKey
Ok "API Key 已配置"

# ── Lite Mode: 仅启动 Python 引擎 + 内置 Lite UI ──
if ($Mode -eq "lite") {
    Step "启动 LikeCodex Lite 模式 (仅 Python 引擎 + 内置 Web UI)..."
    
    # 安装 Python 依赖
    Info "检查 Python 依赖..."
    Push-Location $PROJ
    uv sync --all-packages 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Warn "uv sync 可能未完全成功，继续启动..."
    }
    Pop-Location

    $enginePort = 9090
    
    # 启动 Python 引擎
    Info "启动 Python 引擎 (端口 $enginePort)..."
    $engineJob = Start-Job -Name "likecodex-engine" -ScriptBlock {
        param($root, $port, $key)
        $env:LIKECODEX_LLM_API_KEY = $key
        $env:DEEPSEEK_API_KEY = $key
        $env:LIKECODEX_ENGINE_HOST = "127.0.0.1"
        $env:LIKECODEX_ENGINE_PORT = "$port"
        $env:LIKECODEX_WORKING_DIR = $root
        Set-Location "$root\packages\likecodex-engine"
        uv run python -m likecodex_engine.server
    } -ArgumentList $PROJ, $enginePort, $finalKey

    # 等待引擎启动
    Info "等待引擎就绪..."
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$enginePort/health" -TimeoutSec 2 -ErrorAction Stop
            if ($r.StatusCode -eq 200) { $ready = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 500
    }

    if (-not $ready) {
        Color Red "引擎启动失败，请检查日志。"
        Receive-Job -Job $engineJob
        Color Yellow "按 Enter 键退出..."
        $null = Read-Host
        exit 1
    }
    Ok "引擎已就绪 → http://127.0.0.1:$enginePort"

    $liteUrl = "http://127.0.0.1:$enginePort/lite"
    $apiUrl = "http://127.0.0.1:$enginePort"
    
    # 显示信息
    Clear-Host
    Color Green "╔══════════════════════════════════════════════╗"
    Color Green "║        LikeCodex Lite 已启动!               ║"
    Color Green "╠══════════════════════════════════════════════╣"
    Color Green "║  Lite UI:  $($liteUrl.PadRight(33))║"
    Color Green "║  API:      $($apiUrl.PadRight(33))║"
    Color Green "╠══════════════════════════════════════════════╣"
    Color Green "║  按 Ctrl+C 停止所有服务                      ║"
    Color Green "╚══════════════════════════════════════════════╝"
    
    Start-Process "http://127.0.0.1:$enginePort/lite"

    # 等待 Ctrl+C
    try {
        while ($true) { Start-Sleep -Seconds 1 }
    } finally {
        Step "正在停止服务..."
        Get-Job -Name "likecodex-engine" | Stop-Job
        Get-Job -Name "likecodex-engine" | Remove-Job
        Ok "已停止"
    }
    return
}

# ── Full Mode: 引擎 + Rust API + Next.js Web UI ──

# 设置 MSVC 工具链
if (-not $env:RUSTUP_TOOLCHAIN) {
    $env:RUSTUP_TOOLCHAIN = "stable-x86_64-pc-windows-msvc"
}

if (-not (Get-Command link.exe -ErrorAction SilentlyContinue)) {
    Warn "未检测到 MSVC link.exe。如果构建失败，请安装 Visual Studio Build Tools。"
}

# ── 3. 构建 Rust 工作空间 ──
Step "构建 Rust 工作空间..."

if (-not $SkipBuild) {
    $serverBin = "$PROJ\target\debug\likecodex-server.exe"
    if (-not (Test-Path $serverBin)) {
        Info "编译 likecodex-server (首次构建需要几分钟)..."
        Push-Location $PROJ
        cargo build -p likecodex-server 2>&1 | ForEach-Object { Write-Host $_ }
        if ($LASTEXITCODE -ne 0) {
            Color Red "Rust 构建失败，请检查错误信息。"
            Color Yellow "按 Enter 键退出..."
            $null = Read-Host
            exit 1
        }
        Pop-Location
        Ok "likecodex-server 构建完成"
    } else {
        Ok "likecodex-server 已存在 (使用 -SkipBuild 跳过构建)"
    }
} else {
    Info "跳过 Rust 构建 (-SkipBuild)"
}

# ── 4. 安装 Python 依赖 ──
Step "安装 Python 依赖..."
Push-Location $PROJ
uv sync --all-packages 2>&1 | Out-Null
Pop-Location
Ok "Python 依赖就绪"

# ── 5. 安装 Node.js 依赖 ──
Step "检查 Web UI 依赖..."
if (-not (Test-Path "$PROJ\web\node_modules")) {
    Info "安装 npm 依赖..."
    Push-Location "$PROJ\web"
    npm install 2>&1 | Out-Null
    Pop-Location
    Ok "npm 依赖安装完成"
} else {
    Ok "node_modules 已存在"
}

# ── 6. 启动服务 ──
Step "启动 LikeCodex 服务栈..."

$enginePort = 9090
$serverPort = 8080
$webPort = $Port

# 6a. 启动 Python 引擎
Info "启动 Python 引擎 (端口 $enginePort)..."
$engineJob = Start-Job -Name "likecodex-engine" -ScriptBlock {
    param($root, $port, $key)
    $env:LIKECODEX_LLM_API_KEY = $key
    $env:DEEPSEEK_API_KEY = $key
    $env:LIKECODEX_ENGINE_HOST = "127.0.0.1"
    $env:LIKECODEX_ENGINE_PORT = "$port"
    $env:LIKECODEX_WORKING_DIR = $root
    Set-Location "$root\packages\likecodex-engine"
    uv run python -m likecodex_engine.server
} -ArgumentList $PROJ, $enginePort, $finalKey

# 等待引擎就绪
Info "等待引擎就绪..."
$engineReady = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$enginePort/health" -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $engineReady = $true; break }
    } catch {}
    Start-Sleep -Milliseconds 500
}
if (-not $engineReady) {
    Color Red "引擎启动失败！"
    Receive-Job -Job $engineJob
    Color Yellow "按 Enter 键退出..."
    $null = Read-Host
    exit 1
}
Ok "Python 引擎就绪 → http://127.0.0.1:$enginePort"

# 6b. 启动 Rust API 服务器
Info "启动 Rust API 服务器 (端口 $serverPort)..."
$serverJob = Start-Job -Name "likecodex-server" -ScriptBlock {
    param($root, $port, $enginePort, $key)
    $env:LIKECODEX_LLM_API_KEY = $key
    $env:DEEPSEEK_API_KEY = $key
    $env:LIKECODEX_ENGINE_URL = "http://127.0.0.1:$enginePort"
    $env:LIKECODEX_SERVER_PORT = "$port"
    Set-Location $root
    & "$root\target\debug\likecodex-server.exe"
} -ArgumentList $PROJ, $serverPort, $enginePort, $finalKey

# 等待服务器就绪
$serverReady = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$serverPort/health" -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $serverReady = $true; break }
    } catch {}
    Start-Sleep -Milliseconds 500
}
if (-not $serverReady) {
    Warn "API 服务器可能未完全就绪，Web UI 仍可尝试连接..."
}
Ok "Rust API 服务器就绪 → http://127.0.0.1:$serverPort"

# 6c. 启动 Web UI
Info "启动 Web UI (端口 $webPort)..."
$webJob = Start-Job -Name "likecodex-web" -ScriptBlock {
    param($root, $port)
    $env:PORT = "$port"
    Set-Location "$root\web"
    npm run dev
} -ArgumentList $PROJ, $webPort

Start-Sleep -Seconds 3

# ── 7. 显示信息 ──
Clear-Host
Color Green "╔══════════════════════════════════════════════════╗"
Color Green "║           LikeCodex 已启动!                      ║"
Color Green "╠══════════════════════════════════════════════════╣"
Color Green "║  Web UI:   http://127.0.0.1:$webPort $(if ($webPort -eq 3000) { "(默认)" } else { "" })".PadRight(48) + "║"
Color Green "║  API:      http://127.0.0.1:$serverPort".PadRight(48) + "║"
Color Green "║  Engine:   http://127.0.0.1:$enginePort".PadRight(48) + "║"
Color Green "║  Lite UI:  http://127.0.0.1:$enginePort/lite".PadRight(48) + "║"
Color Green "╠══════════════════════════════════════════════════╣"
Color Green "║  按 Ctrl+C 停止所有服务                           ║"
Color Green "╚══════════════════════════════════════════════════╝"

Start-Process "http://127.0.0.1:$webPort"

# ── 8. 等待关闭 ──
try {
    while ($true) {
        Start-Sleep -Seconds 1
        # 每分钟检查一次子进程状态
        $i++
        if ($i -ge 60) {
            $i = 0
            foreach ($job in @($engineJob, $serverJob, $webJob)) {
                if ($job.State -eq "Failed") {
                    Warn "检测到 $($job.Name) 异常退出:"
                    Receive-Job -Job $job
                }
            }
        }
    }
} finally {
    Step "正在停止所有服务..."
    Get-Job | Stop-Job -ErrorAction SilentlyContinue
    Get-Job | Remove-Job -ErrorAction SilentlyContinue
    Ok "所有服务已停止"
}
