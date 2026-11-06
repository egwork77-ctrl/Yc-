@echo off
REM Double-click to start. Keep this window open while using the iPad.
cd /d "%~dp0"
where py >nul 2>nul && (py -m faultdetect serve --host 0.0.0.0 --port 8000 --data samples) || (python -m faultdetect serve --host 0.0.0.0 --port 8000 --data samples)
echo.
echo If you see an error above, install Python 3.10+ from python.org (check "Add python.exe to PATH").
pause
