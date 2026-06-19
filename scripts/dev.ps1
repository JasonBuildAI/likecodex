# LikeCodex development launcher for Windows.
param(
    [switch]$SkipWeb,
    [switch]$SkipServer
)

$ErrorActionPreference = "Stop"

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
