@echo off
rem Double-click to start FrameCoach. The first run sets everything up.
rem Run "start.bat --update" after pulling a new version to update the dependencies.
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Open PowerShell and run:  winget install Python.Python.3.12
  echo Then close this window and double-click start.bat again.
  pause
  exit /b 1
)

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Creating a Python environment in .venv ...
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)

if not exist ".venv\installed.txt" goto :install
if /i "%~1"=="--update" goto :install
goto :run

:install
echo Installing dependencies. The first time this takes a few minutes ...
"%PY%" -m pip install --upgrade pip
if errorlevel 1 goto :error
"%PY%" -m pip install -e .
if errorlevel 1 goto :error
echo done> ".venv\installed.txt"

:run
"%PY%" -m framecoach serve
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo Something went wrong, see the messages above.
pause
exit /b 1
