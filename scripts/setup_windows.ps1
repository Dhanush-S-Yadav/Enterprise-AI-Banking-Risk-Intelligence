param([switch]$DownloadModel)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
Write-Host '=== Atlas Banking AI - Windows 11 setup ===' -ForegroundColor Cyan
try { & py -3.11 --version | Out-Host } catch { throw 'Python 3.11 is required. Install it from python.org with the Windows launcher selected.' }
if (-not (Test-Path .venv)) { & py -3.11 -m venv .venv }
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed' }
& $Python -m pip install -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Backend Python dependency installation failed' }
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
try { & node --version | Out-Host; & npm --version | Out-Host } catch { throw 'Node.js LTS and npm are required: install from nodejs.org' }
Push-Location frontend
try { & npm install; if ($LASTEXITCODE -ne 0) { throw 'npm install failed' } } finally { Pop-Location }
if ($DownloadModel) {
    try { & ollama --version | Out-Host } catch { throw 'Ollama is not installed. Install it from ollama.com/download/windows' }
    & ollama pull llama3.1:8b
    if ($LASTEXITCODE -ne 0) { throw 'Ollama model download failed' }
}
Write-Host 'Setup complete. In separate terminals run scripts\start_backend.ps1 and scripts\start_frontend.ps1' -ForegroundColor Green
Write-Host 'Use Document Library > Load 24 demo documents to build the initial index.'
