$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create .venv and install backend/requirements.lock first. See README.md.'
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'backend\.env'))) {
    throw 'Create backend/.env from backend/.env.example and configure the model key first.'
}
$env:PYTHONUTF8 = '1'
& $pythonPath -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --no-access-log
