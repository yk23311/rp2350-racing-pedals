param([switch]$Check, [switch]$Legacy, [switch]$Demo)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "GUI environment not found: $python`nRun these commands in the project root first:`n  python -m venv .venv`n  .\.venv\Scripts\python.exe -m pip install -r tools/requirements.txt"
}
if ($Legacy) { & $python -c "import tkinter, serial" 2>$null }
else { & $python -c "from PySide6.QtWidgets import QApplication; import serial" 2>$null }
if ($LASTEXITCODE -ne 0) {
    throw 'GUI dependencies missing. Run .\.venv\Scripts\python.exe -m pip install -r tools/requirements.txt'
}
if ($Check) {
    Write-Host 'GUI environment OK.'
    exit 0
}
Set-Location -LiteralPath $projectRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$entry = if ($Legacy) { 'pedal_gui.py' } else { 'control_center.py' }
$guiArgs = @((Join-Path $PSScriptRoot $entry))
if ($Demo -and -not $Legacy) { $guiArgs += '--demo' }
& $python @guiArgs
exit $LASTEXITCODE
