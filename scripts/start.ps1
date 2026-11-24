param([string]$Workspace = '', [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Please install dependencies first. See README.md.' }
$launcher = Join-Path $PSScriptRoot 'start.py'
if ($Workspace) { & $pythonPath $launcher --workspace $Workspace --port $Port }
else { & $pythonPath $launcher --port $Port }
exit $LASTEXITCODE
