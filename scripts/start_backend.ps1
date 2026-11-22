$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'Run scripts\setup_windows.ps1 first.' }
& $Python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
