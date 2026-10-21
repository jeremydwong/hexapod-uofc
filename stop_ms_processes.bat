@echo off
rem Stop Motion Systems' ForceSeatPM services and app before running our ForceSeatDI tools.
rem They share the platform's USB link with our connection (LABLOG 2026-10-20: pose reads failing
rem with SDK error 2 after sends). Afterwards replug the platform's USB once if reads were failing.
rem Undo: net start "MotionSystems Com64" and net start "MotionSystems AppWatcher64" (or reboot:
rem both are set to start automatically).

net session >nul 2>&1
if errorlevel 1 (
    echo Needs Administrator: asking Windows to re-run this elevated...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo Stopping Motion Systems services...
net stop "MotionSystems AppWatcher64"
net stop "MotionSystems Com64"

echo Closing ForceSeatPM if it is open...
taskkill /IM ForceSeatPM.exe /F >nul 2>&1

echo.
powershell -NoProfile -Command "Get-Service -DisplayName 'MotionSystems*' | Format-Table DisplayName, Status -AutoSize; if (Get-Process ForceSeatPM -ErrorAction SilentlyContinue) { 'ForceSeatPM is STILL running' } else { 'ForceSeatPM not running' }"
echo If the platform's pose reads were failing (SDK error 2), replug its USB cable now.
pause
