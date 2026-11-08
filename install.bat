@echo off
REM Installs MetalEQ's Python dependency (PyQt6) on Windows.
REM
REM NOTE: the audio engine (PulseAudio/PipeWire + GStreamer via PyGObject)
REM only exists on Linux. This installs what the GUI needs; see README.md.
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
    echo Python 3 was not found.
    echo Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^)
    echo and run this script again.
    goto :fail
)

echo Using: %PY%
%PY% --version

echo.
echo ==^> Installing PyQt6
%PY% -m pip install --user -r requirements.txt
if errorlevel 1 (
    echo.
    echo pip failed - see the messages above.
    goto :fail
)

echo.
echo ==^> Verifying
%PY% -c "import PyQt6.QtWidgets; print('  ok   PyQt6')"
if errorlevel 1 (
    echo   FAIL PyQt6 did not import.
    goto :fail
)

echo.
echo ==^> Creating desktop and Start menu shortcuts
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make_shortcuts.ps1"
if errorlevel 1 echo   Could not create shortcuts ^(not fatal^) - run.bat still works.

echo.
echo Done. Start MetalEQ from the desktop icon, or with: run.bat
echo.
echo Reminder: the audio engine is Linux-only ^(PulseAudio/PipeWire + GStreamer^).
pause
exit /b 0

:fail
echo.
pause
exit /b 1
