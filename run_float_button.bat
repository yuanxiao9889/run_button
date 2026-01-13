@echo off
setlocal enabledelayedexpansion

:: --- 1. Define Potential Python Paths ---
set "PY_PATH_1=..\..\..\python_dapao312\python.exe"
set "PY_PATH_2=..\..\..\python_embeded\python.exe"

:: --- 2. Detect Python ---
if exist "%PY_PATH_1%" (
    set "PYTHON=%PY_PATH_1%"
    goto :CHECK_DEPS
)

if exist "%PY_PATH_2%" (
    set "PYTHON=%PY_PATH_2%"
    goto :CHECK_DEPS
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON=python"
    goto :CHECK_DEPS
)

:: No Python found
msg * "No Python environment found! Please ensure Python is installed."
exit /b

:CHECK_DEPS
:: --- 3. Check and Install Dependencies (Silent) ---
"%PYTHON%" -c "import requests, websocket, keyboard" >nul 2>nul
if %errorlevel% neq 0 (
    :: If missing, we MUST show a window briefly to install, otherwise user won't know why it's slow/failing
    echo Installing dependencies...
    "%PYTHON%" -m pip install requests websocket-client keyboard >nul 2>nul
)

:RUN
:: --- 4. Launch Silent ---
:: Construct pythonw path from python path
set "PYTHONW=%PYTHON:python.exe=pythonw.exe%"

:: Check if pythonw exists (it should for standard/embedded installs)
if not exist "%PYTHONW%" (
    :: Fallback to python.exe if pythonw not found (will show window)
    set "PYTHONW=%PYTHON%"
)

:: Use start "" /B to launch in background and exit batch immediately
start "" "%PYTHONW%" float_run.py
exit
