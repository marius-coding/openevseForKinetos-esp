@echo off
setlocal ENABLEDELAYEDEXPANSION

REM -------------------------------------------------------------
REM  OpenEVSE ESP32 Flash Helper (Windows)
REM  Creates/uses a local venv, installs esptool + pyserial, then
REM  launches interactive Python script to flash firmware.
REM  Usage (double-click) or from terminal:
REM     setup_and_flash.bat [optional args passed to python]
REM  Pass --help to see Python script arguments.
REM -------------------------------------------------------------

REM Detect Python (prefer 'python', fallback to 'py -3')
where python >nul 2>&1
if %errorlevel%==0 (
  set "PYTHON_CMD=python"
) else (
  where py >nul 2>&1
  if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
  ) else (
    echo [ERROR] Python 3 not found in PATH. Please install from https://www.python.org/downloads/ and re-run.
    pause
    exit /b 1
  )
)

REM Create virtual environment if missing
if not exist .venv (
  echo [+] Creating virtual environment (.venv)...
  %PYTHON_CMD% -m venv .venv
  if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
  )
)

echo [+] Activating virtual environment
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
  echo [ERROR] Failed to activate virtual environment.
  pause
  exit /b 1
)

echo [+] Upgrading pip (quietly)...
python -m pip install --upgrade pip >nul 2>&1

echo [+] Ensuring required packages (esptool, pyserial) are installed...
python -m pip install --upgrade esptool pyserial >nul
if %errorlevel% neq 0 (
  echo [ERROR] Failed to install Python dependencies.
  pause
  exit /b 1
)

echo.
echo -------------------------------------------------------------
echo  OpenEVSE ESP32 Flash Utility
echo -------------------------------------------------------------
echo.

REM Run the Python flashing script, forwarding any args
python scripts\flash_esp32.py %*
set SCRIPT_ERROR=%errorlevel%

if "%~1"=="--no-pause" goto :end
if "%~2"=="--no-pause" goto :end
if "%~3"=="--no-pause" goto :end

echo.
echo (Close window or press any key to finish)
pause >nul

:end
exit /b %SCRIPT_ERROR%
