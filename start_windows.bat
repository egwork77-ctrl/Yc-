@echo off
REM ===== AOI tool launcher (double-click) =====
REM Keep this window open while using the iPad.
cd /d "%~dp0"
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python not found. Installing Python 3.12 automatically...
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  echo.
  echo ==== Python installed. Close this window and double-click start_windows.bat again. ====
  echo If install failed: download Python from https://www.python.org and check "Add python.exe to PATH".
  pause
  exit /b
)
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8000"
%PY% -m faultdetect serve --host 0.0.0.0 --port 8000 --data samples
echo.
echo The program stopped. See the message above.
pause
