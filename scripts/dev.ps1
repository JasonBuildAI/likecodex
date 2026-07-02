# LikeCodex development launcher for Windows.
param(
    [switch]$SkipWeb,
    [switch]$SkipServer,
    [switch]$SkipEngine,
    [switch]$Parallel
)

$ErrorActionPreference = "Stop"

# Prefer MSVC toolchain on Windows
if ($env:RUSTUP_TOOLCHAIN -eq $null -or $env:RUSTUP_TOOLCHAIN -eq "") {
    $env:RUSTUP_TOOLCHAIN = "stable-x86_64-pc-windows-msvc"
}

if (-not (Get-Command link.exe -ErrorAction SilentlyContinue)) {
    Write-Host "[warn] MSVC link.exe not found. Run: .\scripts\check-prerequisites.ps1 -InstallMsvc" -ForegroundColor Yellow
}

# Build Rust workspace first
Write-Host "==> Building Rust workspace..." -ForegroundColor Cyan
cargo build --workspace

$jobs = @()

# Start Python engine bridge in background
if (-not $SkipEngine) {
    Write-Host "==> Starting Python engine bridge..." -ForegroundColor Cyan
    $jobs += Start-Job -Name "engine" -ScriptBlock {
        param($wd)
        Set-Location $wd
        uv run python -m likecodex_engine.server
    } -ArgumentList $PWD
}

# Start Rust server in background
if (-not $SkipServer) {
    Write-Host "==> Starting Rust API server..." -ForegroundColor Cyan
    $jobs += Start-Job -Name "server" -ScriptBlock {
        param($wd)
        Set-Location $wd
        cargo run -p likecodex-server
    } -ArgumentList $PWD
}

# Start Next.js dev server
if (-not $SkipWeb) {
    Write-Host "==> Starting Web UI..." -ForegroundColor Cyan
    $jobs += Start-Job -Name "web" -ScriptBlock {
        param($wd)
        Set-Location "$wd\web"
        npm run dev
    } -ArgumentList $PWD
}

Write-Host "==> LikeCodex dev environment started." -ForegroundColor Green
Write-Host "    Jobs running: $($jobs.Count)" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop all background jobs." -ForegroundColor Yellow

try {
    while ($true) {
        Start-Sleep -Seconds 3
        foreach ($job in $jobs) {
            $msg = Receive-Job -Job $job -ErrorAction SilentlyContinue
            if ($msg) { Write-Host "[$($job.Name)] $msg" }
            if ($job.State -eq "Failed") {
                Write-Host "[$($job.Name)] FAILED: $( $job.ChildJobs[0].JobStateInfo.Reason )" -ForegroundColor Red
            }
        }
    }
} finally {
    $jobs | Stop-Job -PassThru | Remove-Job
}
# LikeCodex development launcher for Windows.
param(
    [switch]$SkipWeb,
    [switch]$SkipServer
)

$ErrorActionPreference = "Stop"

# Prefer MSVC toolchain on Windows (GNU linker fails on non-ASCII user profile paths).
if ($env:RUSTUP_TOOLCHAIN -eq $null -or $env:RUSTUP_TOOLCHAIN -eq "") {
    $env:RUSTUP_TOOLCHAIN = "stable-x86_64-pc-windows-msvc"
}

if (-not (Get-Command link.exe -ErrorAction SilentlyContinue)) {
    Write-Host "[warn] MSVC link.exe not found. Run: .\scripts\check-prerequisites.ps1 -InstallMsvc" -ForegroundColor Yellow
}

# Build Rust workspace first so the server/CLI binaries exist.
Write-Host "==> Building Rust workspace..." -ForegroundColor Cyan
cargo build

# Start Python engine bridge in background.
$engineJob = $null
if (-not $SkipServer) {
    Write-Host "==> Starting Python engine bridge..." -ForegroundColor Cyan
    $engineJob = Start-Job {
        Set-Location $using:PWD
        uv run python -m likecodex_engine.server
    }
}

# Start Rust server in background.
$serverJob = $null
if (-not $SkipServer) {
    Write-Host "==> Starting Rust API server..." -ForegroundColor Cyan
    $serverJob = Start-Job {
        Set-Location $using:PWD
        cargo run -p likecodex-server
    }
}

# Start Next.js dev server.
if (-not $SkipWeb) {
    Write-Host "==> Starting Web UI..." -ForegroundColor Cyan
    $webJob = Start-Job {
        Set-Location $using:PWD\web
        npm run dev
    }
}

Write-Host "==> LikeCodex dev environment started." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop all background jobs." -ForegroundColor Yellow

try {
    while ($true) {
        Start-Sleep -Seconds 1
        $jobs = @($engineJob, $serverJob, $webJob) | Where-Object { $_ -ne $null }
        foreach ($job in $jobs) {
            Receive-Job -Job $job
        }
    }
} finally {
    Get-Job | Stop-Job
    Get-Job | Remove-Job
}
