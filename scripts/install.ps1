# LikeCodex Windows installer — pip-first approach with optional Rust compilation
$ErrorActionPreference = "Stop"

$Repo = if ($env:LIKECODEX_INSTALL_REPO) { $env:LIKECODEX_INSTALL_REPO } else { "https://github.com/JasonBuildAI/likecodex.git" }
$InstallDir = if ($env:LIKECODEX_INSTALL_DIR) { $env:LIKECODEX_INSTALL_DIR } else { Join-Path $env:USERPROFILE ".likecodex\install" }

Write-Host "==> LikeCodex Installer (pip-first)" -ForegroundColor Cyan
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
if (-not $pythonPath) {
    Write-Host "  [ERROR] Python not found — install Python 3.11+ from https://python.org" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] $pythonVersion at $pythonPath" -ForegroundColor Green

# --- uv (recommended package manager) ---
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "  [..] Installing uv..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}
Write-Host "  [OK] uv" -ForegroundColor Green

# --- Rust/Cargo (optional) ---
$rustAvailable = Get-Command cargo -ErrorAction SilentlyContinue
if ($rustAvailable) {
    $cargoVersion = & cargo --version 2>&1
    Write-Host "  [OK] $cargoVersion (optional)" -ForegroundColor Green
} else {
    Write-Host "  [..] Rust not found — Python-only mode will be used" -ForegroundColor Yellow
    Write-Host "  [..] Install Rust later for enhanced performance: https://rustup.rs" -ForegroundColor DarkYellow
}

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
# Step 3: Install likecodex via pip (primary method)
# ---------------------------------------------------------------
Write-Host "`n[3/7] Installing likecodex via pip (primary method)..." -ForegroundColor Yellow
Push-Location $InstallDir

try {
    # Install engine and all dependencies via uv/pip
    uv sync --all-packages 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] likecodex installed via uv sync" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] uv sync had issues, trying pip install..." -ForegroundColor Yellow
        & pip install -e packages/likecodex-engine 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] likecodex-engine installed via pip" -ForegroundColor Green
        } else {
            Write-Host "  [ERROR] pip install failed" -ForegroundColor Red
        }
    }
} catch {
    Write-Host "  [ERROR] Installation failed: $_" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location

# ---------------------------------------------------------------
# Step 4: Verify Python installation
# ---------------------------------------------------------------
Write-Host "`n[4/7] Verifying Python installation..." -ForegroundColor Yellow
try {
    $verifyOutput = & uv run python -c "import likecodex_engine; print('OK')" 2>&1
    if ($verifyOutput -match "OK") {
        Write-Host "  [OK] likecodex_engine imported successfully" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Verification output: $verifyOutput" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [WARN] Verification skipped (not critical): $_" -ForegroundColor Yellow
}

# ---------------------------------------------------------------
# Step 5: Optional Rust compilation
# ---------------------------------------------------------------
if ($rustAvailable) {
    Write-Host "`n[5/7] Building Rust CLI (optional, for enhanced performance)..." -ForegroundColor Yellow
    Write-Host "  [..] This step is optional. Skip? (Y/n, default Y): " -NoNewline
    $skipRust = Read-Host
    if ($skipRust -ne "n" -and $skipRust -ne "N") {
        Write-Host "  [..] Skipping Rust build. Run later: cargo install --path crates/likecodex-cli --force" -ForegroundColor DarkYellow
    } else {
        Push-Location $InstallDir
        $cargoArgs = @("install", "--path", "crates/likecodex-cli", "--force")
        & cargo $cargoArgs 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] likecodex CLI built (enhanced mode)" -ForegroundColor Green
        } else {
            Write-Host "  [WARN] CLI build failed — Python-only mode still works" -ForegroundColor Yellow
        }
        Pop-Location
    }
} else {
    Write-Host "`n[5/7] Skipping Rust build (not available)" -ForegroundColor DarkYellow
    Write-Host "  [..] Using Python-only mode" -ForegroundColor Green
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
# Step 7: Verify and finish
# ---------------------------------------------------------------
Write-Host "`n[7/7] Installation complete!" -ForegroundColor Cyan
Write-Host "  Run: likecodex --doctor (check setup)" -ForegroundColor White
Write-Host "  Run: likecodex --setup (configure API key)" -ForegroundColor White
Write-Host "  Run: likecodex --web   (start Web UI)" -ForegroundColor White
Write-Host "`n==> Happy coding with LikeCodex!" -ForegroundColor Cyan
