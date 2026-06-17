# Start LINE webhook server and ngrok
# Usage: .\start.ps1

$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
$Port = 5001

Set-Location $ProjectDir

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env - please check your tokens." -ForegroundColor Yellow
    } else {
        Write-Error ".env not found. Set LINE tokens first."
    }
}

$inUse = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($inUse) {
    Write-Host "Port $Port is already in use. Flask may already be running." -ForegroundColor Yellow
} else {
    Write-Host "Starting Flask server on port $Port..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "Set-Location '$ProjectDir'; python save_line_image.py"
    ) -WindowStyle Normal
    Start-Sleep -Seconds 3
}

Write-Host ""
Write-Host "Starting ngrok..." -ForegroundColor Cyan
Write-Host "Set LINE Webhook URL to: https://YOUR-NGROK-URL/callback" -ForegroundColor Green
Write-Host "Press Ctrl+C in this window to stop ngrok." -ForegroundColor Gray
Write-Host ""

ngrok http $Port
