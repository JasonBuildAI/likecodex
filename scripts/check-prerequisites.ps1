# Verify Rust/Python/Web prerequisites for LikeCodex development on Windows.
param(
    [switch]$InstallMsvc
)

$ErrorActionPreference = "Stop"
$failed = $false

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

Write-Host "==> Checking prerequisites..." -ForegroundColor Cyan

if (-not (Test-Command "rustc")) {
    Write-Host "[fail] Rust not found. Install from https://rustup.rs/" -ForegroundColor Red
    $failed = $true
} else {
    Write-Host "[ok] rustc $(rustc --version)"
}

if (-not (Test-Command "link.exe")) {
    Write-Host "[fail] MSVC link.exe not found (required for Rust on Windows)." -ForegroundColor Red
    Write-Host "       Install: winget install Microsoft.VisualStudio.2022.BuildTools" -ForegroundColor Yellow
    Write-Host "       Then add workload: Microsoft.VisualStudio.Workload.VCTools" -ForegroundColor Yellow
    if ($InstallMsvc) {
        winget install --id Microsoft.VisualStudio.2022.BuildTools -e `
            --accept-package-agreements --accept-source-agreements `
            --override "--wait --passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
    } else {
        $failed = $true
    }
} else {
    Write-Host "[ok] link.exe found"
}

if (-not (Test-Command "uv")) {
    Write-Host "[fail] uv not found. Install from https://github.com/astral-sh/uv" -ForegroundColor Red
    $failed = $true
} else {
    Write-Host "[ok] uv $(uv --version)"
}

if (-not (Test-Command "node")) {
    Write-Host "[fail] Node.js not found." -ForegroundColor Red
    $failed = $true
} else {
    Write-Host "[ok] node $(node --version)"
}

if ($failed) {
    exit 1
}

Write-Host "==> All prerequisites satisfied." -ForegroundColor Green
