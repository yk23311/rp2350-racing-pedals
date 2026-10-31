param([switch]$Check)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "GUI environment not found: $python`nRun these commands in the project root first:`n  python -m venv .venv`n  .\.venv\Scripts\python.exe -m pip install -r tools/requirements.txt"
}
& $python -c "import tkinter" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'This Python does not provide tkinter; rebuild .venv with a Windows Python that includes Tk.'
}
if ($Check) {
    Write-Host 'GUI environment OK.'
    exit 0
}
Set-Location -LiteralPath $projectRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
& $python (Join-Path $PSScriptRoot 'pedal_gui.py')
exit $LASTEXITCODE
