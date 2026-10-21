@echo off
rem Restart Motion Systems' ForceSeatPM services (undo stop_ms_processes.bat), so ForceSeatPM works
rem again for other users. Our tools refuse to connect while these run.

net session >nul 2>&1
if errorlevel 1 (
    echo Needs Administrator: asking Windows to re-run this elevated...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo Starting Motion Systems services...
net start "MotionSystems Com64"
net start "MotionSystems AppWatcher64"
echo.
powershell -NoProfile -Command "Get-Service -DisplayName 'MotionSystems*' | Format-Table DisplayName, Status -AutoSize"
pause
