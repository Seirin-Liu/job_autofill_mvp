@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 (
  echo Failed to enter project directory.
  pause
  exit /b 1
)

if not exist "data" mkdir "data"
if not exist "data\assets" mkdir "data\assets"

set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PY_CMD=py -3"
if not defined PY_CMD (
  where python >nul 2>nul
  if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
  echo Python 3 was not found in PATH.
  echo Install Python 3.10 or newer and enable Add Python to PATH.
  pause
  popd
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PY_CMD% -m venv .venv
  if errorlevel 1 goto :fail
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 goto :fail

if not exist ".env" copy /Y ".env.example" ".env" >nul

echo.
echo Installation completed.
echo Run start.bat to start the backend.
pause
popd
exit /b 0

:fail
echo.
echo Installation failed with code %ERRORLEVEL%.
pause
popd
exit /b 1
