@echo off
REM Launches MetalEQ on Windows. Run install.bat first if PyQt6 is missing.
REM
REM NOTE: the audio engine (PulseAudio/PipeWire + GStreamer via PyGObject)
REM only exists on Linux. If the app exits with "No module named 'gi'",
REM that is why - see README.md.
setlocal
cd /d "%~dp0"

set "PY="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    echo Python 3 was not found. Run install.bat first.
    pause
    exit /b 1
)

%PY% -c "import PyQt6.QtWidgets" >nul 2>&1
if errorlevel 1 (
    echo PyQt6 is not installed. Run install.bat first.
    pause
    exit /b 1
)

%PY% main.py %*
set "RC=%errorlevel%"
if not "%RC%"=="0" (
    echo.
    echo MetalEQ exited with an error ^(code %RC%^).
    echo If the message above mentions "gi": the audio engine is Linux-only.
    pause
)
exit /b %RC%
