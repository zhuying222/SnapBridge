$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)
$venvPython = Join-Path (Join-Path $repoRoot ".venv") "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    throw "Missing Python venv at $venvPython"
}

Push-Location $scriptDir
try {
    & $venvPython -m pip install -r requirements.txt
    & $venvPython -m pip install pyinstaller
    & $venvPython tools\build_sender_icon.py
    & $venvPython -m PyInstaller --noconfirm --clean SnapBridgeSender.spec
}
finally {
    Pop-Location
}
