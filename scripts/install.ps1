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
