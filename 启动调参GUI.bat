@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\start_gui.ps1"
if errorlevel 1 (
    echo.
    echo GUI failed to start. See the error above.
    pause
)
endlocal
