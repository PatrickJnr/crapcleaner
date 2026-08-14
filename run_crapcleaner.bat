@echo off
setlocal enabledelayedexpansion
title CrapCleaner
cd /d "%~dp0"

set "PYTHON=python"
set "VENV_DIR=%~dp0.venv"
set "PY_EXE=%VENV_DIR%\Scripts\python.exe"
set "REQUIREMENTS=%~dp0requirements.txt"

REM ---------------------------------------------------------------
REM CrapCleaner - one-click install & run
REM   - creates a virtual environment on first run
REM   - installs dependencies from requirements.txt
REM   - launches the app (GUI by default)
REM
REM Usage:
REM   run_crapcleaner.bat            -> install (if needed) + open GUI
REM   run_crapcleaner.bat --scan     -> run a CLI scan
REM   run_crapcleaner.bat --gui      -> force GUI
REM ---------------------------------------------------------------

if "%~1"=="--help" goto :help
if "%~1"=="/?" goto :help

REM ---------------- locate Python ----------------
where %PYTHON% >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on PATH.
    echo         Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
    echo         You can also set PYTHON=full\path\to\python.exe above.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('%PYTHON% -c "import sys;print('%%d.%%d'%%sys.version_info[:2])"') do set "PYVERSION=%%v"
echo [OK] Python %PYVERSION% found.

REM ---------------- create venv if missing ----------------
if not exist "%PY_EXE%" (
    echo [..] Creating virtual environment...
    %PYTHON% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
)

REM ---------------- install dependencies ----------------
echo [..] Checking dependencies...
"%PY_EXE%" -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo [..] Installing dependencies - first run, this can take a minute...
    "%PY_EXE%" -m pip install --upgrade pip >nul
    "%PY_EXE%" -m pip install -r "%REQUIREMENTS%"
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed.
        pause
        exit /b 1
    )
    echo [OK] Dependencies installed.
) else (
    echo [OK] Dependencies already installed.
)

REM ---------------- run ----------------
set "ARGS="
:loopargs
if "%~1"=="" goto :run
set "ARGS=%ARGS% %~1"
shift
goto :loopargs

:run
echo [..] Launching CrapCleaner...
if not defined ARGS set "ARGS= --gui"
"%PY_EXE%" -m crapcleaner%ARGS%
set "EXITCODE=%errorlevel%"
echo.
echo [..] CrapCleaner exited with code %EXITCODE%.
pause
exit /b %EXITCODE%

:help
echo CrapCleaner launcher
echo.
echo Usage:  run_crapcleaner.bat [options]
echo.
echo   (no args)   Install if needed, then open the GUI
echo   --gui       Open the graphical interface
echo   --scan      Run a CLI scan and print reclaimable space
echo   --clean-safe Clean all SAFE + LOW_RISK categories (dry run by default)
echo               Add --execute to actually delete, --yes to skip the prompt
echo   --help      Show this help
echo.
exit /b 0
