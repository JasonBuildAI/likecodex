# LikeCodex Windows installer — enhanced with environment detection & auto-config
$ErrorActionPreference = "Stop"

$Repo = if ($env:LIKECODEX_INSTALL_REPO) { $env:LIKECODEX_INSTALL_REPO } else { "https://github.com/JasonBuildAI/likecodex.git" }
$InstallDir = if ($env:LIKECODEX_INSTALL_DIR) { $env:LIKECODEX_INSTALL_DIR } else { Join-Path $env:USERPROFILE ".likecodex\install" }

Write-Host "==> LikeCodex installer (Phase 8.4 enhanced)" -ForegroundColor Cyan
Write-Host "    Target: $InstallDir"

# ---------------------------------------------------------------
# Step 1: Prerequisites detection
# ---------------------------------------------------------------
Write-Host "`n[1/7] Detecting prerequisites..." -ForegroundColor Yellow

# --- Git ---
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git is required — install from https://git-scm.com/download/win"
}
Write-Host "  [OK] git" -ForegroundColor Green

# --- Python ---
$pythonPath = $null
$pythonVersion = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonVersion = & python --version 2>&1
    $pythonPath = (Get-Command python).Source
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonVersion = & python3 --version 2>&1
    $pythonPath = (Get-Command python3).Source
}
if ($pythonPath) {
    Write-Host "  [OK] $pythonVersion at $pythonPath" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Python not found — attempting install..." -ForegroundColor Yellow
    Write-Host "  Please install Python 3.11+ from https://python.org" -ForegroundColor Red
    Write-Host "  After installation, re-run this script." -ForegroundColor Red
}

# --- uv (Python package manager) ---
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "  [..] Installing uv..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "uv installation failed — please install manually from https://docs.astral.sh/uv/"
    }
}
Write-Host "  [OK] uv" -ForegroundColor Green

# --- Node.js ---
$nodeVersion = $null
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeVersion = & node --version 2>&1
    Write-Host "  [OK] Node.js $nodeVersion" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Node.js not found — frontend build will be skipped" -ForegroundColor Yellow
    Write-Host "  Install from https://nodejs.org (v20+ recommended)" -ForegroundColor DarkYellow
}

# --- Rust/Cargo ---
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    Write-Host "  [..] Rust not found — installing via rustup..." -ForegroundColor Yellow
    # Download and run rustup-init.exe silently
    $rustupPath = "$env:TEMP\rustup-init.exe"
    irm -Uri "https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe" -OutFile $rustupPath
    & $rustupPath -y --default-toolchain stable --profile default 2>&1 | Out-Null
    $env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"
    if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
        throw "Rust install failed — install from https://rustup.rs"
    }
}
$cargoVersion = & cargo --version 2>&1
Write-Host "  [OK] $cargoVersion" -ForegroundColor Green

# --- Docker (optional) ---
$dockerAvailable = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerAvailable) {
    Write-Host "  [OK] docker" -ForegroundColor Green
} else {
    Write-Host "  [..] docker not found (optional, for sandbox)" -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------
# Step 2: Clone / update repository
# ---------------------------------------------------------------
Write-Host "`n[2/7] Cloning/updating repository..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
if (-not (Test-Path (Join-Path $InstallDir ".git"))) {
    git clone --depth 1 $Repo $InstallDir
    Write-Host "  [OK] cloned $Repo" -ForegroundColor Green
} else {
    git -C $InstallDir pull --ff-only
    Write-Host "  [OK] updated" -ForegroundColor Green
}

# ---------------------------------------------------------------
# Step 3: Python dependencies
# ---------------------------------------------------------------
Write-Host "`n[3/7] Installing Python dependencies..." -ForegroundColor Yellow
Push-Location $InstallDir
uv sync --all-packages 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [WARN] uv sync had warnings" -ForegroundColor Yellow
} else {
    Write-Host "  [OK] Python dependencies installed" -ForegroundColor Green
}
Pop-Location

# ---------------------------------------------------------------
# Step 4: Build Rust CLI
# ---------------------------------------------------------------
Write-Host "`n[4/7] Building Rust CLI..." -ForegroundColor Yellow
Push-Location $InstallDir
$cargoArgs = @("install", "--path", "crates/likecodex-cli", "--force")
if ($env:LIKECODEX_CARGO_PROFILE -eq "release") {
    $cargoArgs = @("install", "--path", "crates/likecodex-cli", "--force")
}
& cargo $cargoArgs 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] likecodex CLI built" -ForegroundColor Green
} else {
    Write-Host "  [WARN] CLI build failed — check Rust toolchain" -ForegroundColor Yellow
}
Pop-Location

# ---------------------------------------------------------------
# Step 5: Install frontend dependencies (optional)
# ---------------------------------------------------------------
$webDir = Join-Path $InstallDir "web"
if ($nodeVersion -and (Test-Path $webDir)) {
    Write-Host "`n[5/7] Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location $webDir
    if (Test-Path "package.json") {
        & npm install --silent 2>&1 | Out-Null
        Write-Host "  [OK] frontend dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "  [..] no package.json found, skipping" -ForegroundColor DarkYellow
    }
    Pop-Location
} else {
    Write-Host "`n[5/7] Skipping frontend (Node.js not available)" -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------
# Step 6: Create default config
# ---------------------------------------------------------------
Write-Host "`n[6/7] Creating default configuration..." -ForegroundColor Yellow
$ConfigDir = Join-Path $env:USERPROFILE ".likecodex"
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
$ConfigPath = Join-Path $ConfigDir "config.toml"
if (-not (Test-Path $ConfigPath)) {
@'
[llm]
provider = "deepseek"
model = "deepseek-v4-flash"

[approval]
mode = "auto"

[agent]
planner_model = "deepseek-v4-pro"
executor_model = "deepseek-v4-flash"
compact_ratio = 0.8
enable_planner = false

[mcp]
enabled = false

[sandbox]
enabled = false
allow_fallback = true
'@ | Set-Content -Path $ConfigPath -Encoding UTF8
    Write-Host "  [OK] config created at $ConfigPath" -ForegroundColor Green
} else {
    Write-Host "  [..] config already exists, keeping yours" -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------
# Step 7: Verify installation
# ---------------------------------------------------------------
Write-Host "`n[7/7] Verifying installation..." -ForegroundColor Yellow
$cliPath = Join-Path $env:USERPROFILE ".cargo\bin\likecodex.exe"
if (Test-Path $cliPath) {
    Write-Host "  [OK] likecodex CLI at $cliPath" -ForegroundColor Green
} elseif (Get-Command likecodex -ErrorAction SilentlyContinue) {
    Write-Host "  [OK] likecodex CLI found in PATH" -ForegroundColor Green
} else {
    Write-Host "  [WARN] likecodex not found in PATH — add %USERPROFILE%\.cargo\bin to PATH" -ForegroundColor Yellow
}

Write-Host "`n==> Installation complete!" -ForegroundColor Cyan
Write-Host "    Run: likecodex doctor; likecodex code" -ForegroundColor White
# LikeCodex Windows installer
$ErrorActionPreference = "Stop"

$Repo = if ($env:LIKECODEX_INSTALL_REPO) { $env:LIKECODEX_INSTALL_REPO } else { "https://github.com/JasonBuildAI/likecodex.git" }
$InstallDir = if ($env:LIKECODEX_INSTALL_DIR) { $env:LIKECODEX_INSTALL_DIR } else { Join-Path $env:USERPROFILE ".likecodex\install" }

Write-Host "==> LikeCodex installer"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git is required"
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..."
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "Rust/cargo is required — install from https://rustup.rs"
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
if (-not (Test-Path (Join-Path $InstallDir ".git"))) {
    git clone $Repo $InstallDir
} else {
    git -C $InstallDir pull --ff-only
}

Push-Location $InstallDir
uv sync --all-packages
cargo install --path crates/likecodex-cli --force
Pop-Location

$ConfigDir = Join-Path $env:USERPROFILE ".likecodex"
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
$ConfigPath = Join-Path $ConfigDir "config.toml"
if (-not (Test-Path $ConfigPath)) {
@'
[llm]
provider = "deepseek"
model = "deepseek-v4-flash"

[approval]
mode = "auto"

[agent]
planner_model = "deepseek-v4-pro"
executor_model = "deepseek-v4-flash"
compact_ratio = 0.8
enable_planner = false
'@ | Set-Content -Path $ConfigPath -Encoding UTF8
}

Write-Host "==> Done. Run: likecodex doctor; likecodex code"
