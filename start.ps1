$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    $python = "python"
}

function Test-PortInUse([int] $port) {
    return $null -ne (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

if (Test-PortInUse 8000) {
    Write-Host "Backend already running on port 8000"
} else {
    Start-Process powershell.exe -WorkingDirectory $backend -ArgumentList @(
        "-NoExit",
        "-Command",
        "& '$python' -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000"
    )
}

if (Test-PortInUse 5173) {
    Write-Host "Frontend already running on port 5173"
} else {
    Start-Process powershell.exe -WorkingDirectory $frontend -ArgumentList @(
        "-NoExit",
        "-Command",
        "npm run dev -- --host 0.0.0.0"
    )
}

Write-Host "Backend:  http://localhost:8000"
Write-Host "Frontend: http://localhost:5173"
