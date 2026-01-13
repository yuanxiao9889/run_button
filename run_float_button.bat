@echo off
setlocal enabledelayedexpansion

:: --- 1. Detect ComfyUI Embedded Python ---
set "EMBEDDED_PYTHON=..\..\..\python_dapao312\python.exe"
if exist "%EMBEDDED_PYTHON%" (
    echo [INFO] Detected ComfyUI Embedded Python.
    set "PYTHON=%EMBEDDED_PYTHON%"
    set "PYTHONW=!PYTHON:python.exe=pythonw.exe!"
    if not exist "!PYTHONW!" set "PYTHONW=!PYTHON!"
    goto :RUN
)

:: --- 2. Detect System Python ---
where python >nul 2>nul
if %errorlevel% equ 0 (
    echo [INFO] Detected System Python.
    set "PYTHON=python"
    set "PYTHONW=pythonw"
    
    :: Check if dependencies are installed for system python
    echo Checking dependencies...
    !PYTHON! -c "import requests, websocket, keyboard" >nul 2>nul
    if !errorlevel! neq 0 (
        echo [INFO] Installing required libraries...
        !PYTHON! -m pip install requests websocket-client keyboard
    )
    goto :RUN
)

:: --- 3. No Python Found ---
echo [ERROR] No Python environment found!
echo Please ensure this script is either:
echo   1. Inside ComfyUI\custom_nodes\run_button (for local use)
echo   2. Or you have Python installed on your computer (for remote use)
pause
exit /b

:RUN
echo Starting Run Button...
start "" "%PYTHONW%" float_run.py
exit
