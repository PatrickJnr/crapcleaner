@echo off
REM ============================================================
REM  CrapCleaner build script - packages the Python app into a
REM  standalone Windows executable with PyInstaller.
REM
REM  Usage:
REM    scriptsuild_windows.bat          one-file GUI exe (dist\CrapCleaner.exe)
REM    scriptsuild_windows.bat onedir   folder build, faster startup
REM                        (dist\CrapCleaner\CrapCleaner.exe)
REM
REM  Requires: Python 3.10+ with PySide6. PyInstaller is installed
REM  automatically if missing. Prefers the project .venv if present.
REM ============================================================
setlocal
cd /d "%~dp0.."

REM Prefer the project virtualenv, otherwise fall back to system python.
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo [build] Using: %PY%

%PY% -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo [build] ERROR: PySide6 is not installed in the selected Python.
    exit /b 1
)

%PY% -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [build] PyInstaller not found - installing...
    %PY% -m pip install pyinstaller
    if errorlevel 1 (
        echo [build] ERROR: failed to install PyInstaller.
        exit /b 1
    )
)

set "MODE=onefile"
if /I "%~1"=="onedir" set "MODE=onedir"

REM Font assets must be bundled so icons render in the frozen exe.
set "DATAFLAG=--add-data "crapcleaner/assets;crapcleaner/assets""

echo [build] Building %MODE% executable...
if "%MODE%"=="onefile" (
    %PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name CrapCleaner %DATAFLAG% scripts/launcher.py
) else (
    %PY% -m PyInstaller --noconfirm --clean --onedir --windowed --name CrapCleaner %DATAFLAG% scripts/launcher.py
)
if errorlevel 1 (
    echo [build] ERROR: build failed.
    exit /b 1
)

echo.
echo [build] Done.
if "%MODE%"=="onefile" (
    echo [build] Executable: dist\CrapCleaner.exe
) else (
    echo [build] Executable: dist\CrapCleaner\CrapCleaner.exe
)
echo [build] Note: the exe is built on this machine and may trigger
echo [build] SmartScreen warnings because it is not code-signed.
endlocal
