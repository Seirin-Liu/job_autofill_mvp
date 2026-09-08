@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 (
  echo Failed to enter project directory.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment not found.
  echo Please run install.bat first.
  pause
  popd
  exit /b 1
)

echo Starting Job Autofill backend at http://127.0.0.1:8765
".venv\Scripts\python.exe" -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Backend exited with code %EXIT_CODE%.
  pause
)
popd
exit /b %EXIT_CODE%
