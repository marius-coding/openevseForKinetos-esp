@echo off
setlocal ENABLEDELAYEDEXPANSION
REM ---------------------------------------------------------------------------
REM LGT8F328P Flash Helper (Windows)
REM
REM Requirements:
REM   * avrdude.exe available in PATH or placed beside this script.
REM   * A USB serial adapter / onboard programmer (e.g. CH340, CP2102) -> COMx
REM
REM Usage Examples:
REM   flash_lgt8f328p.bat -f build\open_evse.ino.hex -p COM5
REM   flash_lgt8f328p.bat -f firmware.hex -p COM3 -b 57600
REM   flash_lgt8f328p.bat -y -f firmware.hex -p COM4
REM ---------------------------------------------------------------------------

set HEX_FILE=
set PORT=
set BAUD=115200
set PROGRAMMER=avrisp
set PART=lgt8f328p
set EXTRA_ARGS=
set NON_INTERACTIVE=0

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="-f" ( set HEX_FILE=%~2 & shift & shift & goto parse_args )
if /I "%~1"=="-p" ( set PORT=%~2 & shift & shift & goto parse_args )
if /I "%~1"=="-b" ( set BAUD=%~2 & shift & shift & goto parse_args )
if /I "%~1"=="-P" ( set PROGRAMMER=%~2 & shift & shift & goto parse_args )
if /I "%~1"=="-a" ( set EXTRA_ARGS=%~2 & shift & shift & goto parse_args )
if /I "%~1"=="-y" ( set NON_INTERACTIVE=1 & shift & goto parse_args )
if /I "%~1"=="-h" ( goto :usage )
shift
goto parse_args

:args_done

:find_avrdude
where avrdude >nul 2>&1
if not errorlevel 1 goto avrdude_ok
REM Try local directory
if exist "%~dp0avrdude.exe" (
  set PATH=%PATH%;%~dp0
  where avrdude >nul 2>&1 && goto avrdude_ok
)
echo [WARN] avrdude not found in PATH.
echo Install via e.g. WinAVR or Arduino toolchain, or place avrdude.exe next to this script.
if %NON_INTERACTIVE%==1 (
  echo [ERROR] avrdude missing (non-interactive).
  exit /b 1
)
set /p CONT="Continue after installing avrdude? (y/N): "
if /I not "%CONT%"=="Y" if /I not "%CONT%"=="YES" exit /b 1
where avrdude >nul 2>&1 || ( echo [ERROR] Still not found. & exit /b 1 )
:avrdude_ok

REM HEX file prompt
if not defined HEX_FILE (
  if %NON_INTERACTIVE%==1 ( echo [ERROR] Missing -f HEX file & exit /b 2 )
  rem Auto-detect .hex files in current directory
  set COUNT=0
  for %%F in (*.hex) do (
    if exist "%%~F" (
      set /a COUNT+=1
      set HEX_CAND_!COUNT!=%%~F
    )
  )
  if %COUNT%==1 (
    for %%I in (1) do set ONE_FILE=!HEX_CAND_1!
    set /p USEONE="Found HEX file '%ONE_FILE%'. Use this? [Y/n]: "
    if /I "!USEONE!"=="" set USEONE=Y
    if /I "!USEONE!"=="Y" set HEX_FILE=%ONE_FILE%
  ) else if %COUNT% GTR 1 (
    echo Multiple HEX files found:
    for /L %%I in (1,1,%COUNT%) do echo   %%I) !HEX_CAND_%%I!
    set /p PICK="Select file [1-%COUNT%] or leave blank to enter path: "
    if defined PICK (
      for /f "delims=0123456789" %%A in ("!PICK!") do set INVALID=1
      if not defined INVALID if %PICK% GEQ 1 if %PICK% LEQ %COUNT% (
        for %%I in ( %PICK% ) do set HEX_FILE=!HEX_CAND_%%I!
      )
    )
  )
  if not defined HEX_FILE set /p HEX_FILE="Enter path to HEX file: "
)
if not exist "%HEX_FILE%" (
  echo [ERROR] HEX file not found: %HEX_FILE%
  exit /b 2
)
for %%I in ("%HEX_FILE%") do set HEX_FILE_FULL=%%~fI

REM Port prompt
if not defined PORT (
  if %NON_INTERACTIVE%==1 ( echo [ERROR] Missing -p port & exit /b 2 )
  echo Available COM ports (heuristic):
  for /f "tokens=1 delims=" %%C in ('wmic path Win32_SerialPort get DeviceID ^| find "COM"') do echo   %%C
  set /p PORT="Enter COM port (e.g. COM5): "
)

echo [+] Flashing %HEX_FILE_FULL% to %PART% via %PROGRAMMER% on %PORT% @ %BAUD%
set CMD=avrdude -p %PART% -c %PROGRAMMER% -P %PORT% -b %BAUD% -U flash:w:%HEX_FILE_FULL%:i %EXTRA_ARGS%
echo [CMD] %CMD%
%CMD%
set RET=%ERRORLEVEL%
if not %RET%==0 (
  echo [ERROR] avrdude exited with code %RET%
  exit /b %RET%
)
echo [+] Done.
exit /b 0

:usage
echo LGT8F328P Flash Helper
echo.
echo Options:
echo   -f ^<file^>     HEX file to flash
echo   -p ^<port^>     COM port (e.g. COM5)
echo   -b ^<baud^>     Baud rate (default 115200)
echo   -P ^<prog^>     Programmer (default avrisp)
echo   -a ^<args^>     Extra avrdude args (quoted)
echo   -y           Non-interactive (fail if missing args)
echo   -h           This help
echo.
echo Examples:
echo   flash_lgt8f328p.bat -f build\open_evse.ino.hex -p COM5
echo   flash_lgt8f328p.bat -f firmware.hex -p COM3 -b 57600
exit /b 0
