# LikeCodex Full Stack Launcher
# Starts: Python Engine (9091) + Rust Server (8080) + Next.js Web UI (3000)

$ErrorActionPreference = "Stop"
$PROJ = Split-Path -Parent $PSScriptRoot

Write-Host "`n[LikeCodex] Starting full stack..." -ForegroundColor Cyan

# 1. Start Python Engine on port 9091
Write-Host "[1/3] Starting Python Engine on port 9091..." -ForegroundColor Yellow
Start-Process -FilePath "powershell" `
    -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$PROJ\packages\likecodex-engine\start-engine.ps1" `
    -WorkingDirectory "$PROJ\packages\likecodex-engine" `
    -NoNewWindow -PassThru | Out-Null

# Wait for engine
for ($i = 0; $i -lt 60; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:9091/health" -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { Write-Host "✓ Engine ready" -ForegroundColor Green; break }
    } catch {}
    Start-Sleep -Milliseconds 500
}

# 2. Start Rust Server on port 8080
Write-Host "[2/3] Starting Rust Server on port 8080..." -ForegroundColor Yellow
$env:LIKECODEX_ENGINE_URL = "http://127.0.0.1:9091"
$env:LIKECODEX_SERVER_PORT = "8080"
Start-Process -FilePath "$PROJ\target\debug\likecodex-server.exe" `
    -WorkingDirectory $PROJ `
    -NoNewWindow -PassThru | Out-Null

# Wait for server
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/health" -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { Write-Host "✓ Server ready" -ForegroundColor Green; break }
    } catch {}
    Start-Sleep -Milliseconds 500
}

# 3. Start Next.js Web UI on port 3000
Write-Host "[3/3] Starting Web UI on port 3000..." -ForegroundColor Yellow
Start-Process -FilePath "npm" `
    -ArgumentList "run", "dev" `
    -WorkingDirectory "$PROJ\web" `
    -NoNewWindow -PassThru | Out-Null

# Wait for web UI
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { Write-Host "✓ Web UI ready" -ForegroundColor Green; break }
    } catch {}
    Start-Sleep -Milliseconds 500
}

Write-Host "`n[LikeCodex] All services started!" -ForegroundColor Green
Write-Host "  Engine:   http://127.0.0.1:9091" -ForegroundColor White
Write-Host "  API:      http://127.0.0.1:8080" -ForegroundColor White
Write-Host "  Web UI:   http://127.0.0.1:3000" -ForegroundColor White
Write-Host "  Lite UI:  http://127.0.0.1:9091/lite" -ForegroundColor White
Write-Host "`nPress Ctrl+C to stop all services..." -ForegroundColor Yellow

try {
    while ($true) { Start-Sleep -Seconds 1 }
} finally {
    Write-Host "`nStopping all services..." -ForegroundColor Yellow
    Stop-Process -Name "python", "uv", "node", "likecodex-server" -Force -ErrorAction SilentlyContinue
    Write-Host "All services stopped." -ForegroundColor Green
}
