param([switch]$SkipInstall)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) { throw 'Windows x64 is required.' }
function Invoke-Checked([string]$Program,[string[]]$Arguments) { & $Program @Arguments; if ($LASTEXITCODE -ne 0) { throw "Command failed: $Program (exit $LASTEXITCODE)" } }
$pythonPath=Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { Invoke-Checked 'python' @('-m','venv','.venv') }
Invoke-Checked $pythonPath @('--version')
Invoke-Checked 'node' @('--version')
if (-not $SkipInstall) {
 Invoke-Checked $pythonPath @('-m','pip','install','-r','backend/requirements.lock.txt','-r','backend/requirements-build.txt')
 Push-Location frontend
 try { Invoke-Checked 'npm.cmd' @('ci','--no-audit','--no-fund') } finally { Pop-Location }
 Push-Location desktop
 try { Invoke-Checked 'npm.cmd' @('ci','--no-audit','--no-fund') } finally { Pop-Location }
}
Invoke-Checked $pythonPath @('scripts/make_desktop_icon.py')
Push-Location frontend
try { Invoke-Checked 'npm.cmd' @('run','build') } finally { Pop-Location }
Invoke-Checked $pythonPath @('-m','PyInstaller','--noconfirm','--distpath','build/backend','--workpath','build/pyinstaller','backend/desktop.spec')
$env:CSC_IDENTITY_AUTO_DISCOVERY='false'
Push-Location desktop
try { Invoke-Checked 'npm.cmd' @('run','dist') } finally { Pop-Location }
$appVersion=(Get-Content -LiteralPath (Join-Path $projectRoot 'desktop/package.json') -Raw | ConvertFrom-Json).version
$installer=Join-Path $projectRoot ('release/ResearchHub-Setup-'+$appVersion+'-x64.exe')
if (-not (Test-Path -LiteralPath $installer)) { throw 'Installer was not generated.' }
Get-Item -LiteralPath $installer | Select-Object FullName,Length,LastWriteTime
Get-FileHash -LiteralPath $installer -Algorithm SHA256
