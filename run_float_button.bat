@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo       ComfyUI Run Button - Launch Script
echo ========================================================

:: --- 1. Define Potential Python Paths ---
:: Priority 1: User's specific embedded python (python_dapao312)
set "PY_PATH_1=..\..\..\python_dapao312\python.exe"
:: Priority 2: Standard ComfyUI embedded python (python_embeded)
set "PY_PATH_2=..\..\..\python_embeded\python.exe"

:: --- 2. Detect Python ---
if exist "%PY_PATH_1%" (
    echo [INFO] Detected Embedded Python: %PY_PATH_1%
    set "PYTHON=%PY_PATH_1%"
    goto :CHECK_DEPS
)

if exist "%PY_PATH_2%" (
    echo [INFO] Detected Embedded Python: %PY_PATH_2%
    set "PYTHON=%PY_PATH_2%"
    goto :CHECK_DEPS
)

:: Priority 3: System Python
where python >nul 2>nul
if %errorlevel% equ 0 (
    echo [INFO] Detected System Python.
    set "PYTHON=python"
    goto :CHECK_DEPS
)

:: --- 3. No Python Found ---
echo [ERROR] No Python environment found!
echo Please ensure this script is either:
echo   1. Inside ComfyUI\custom_nodes\run_button (for local use)
echo   2. Or you have Python installed on your computer (for remote use)
pause
exit /b

:CHECK_DEPS
:: --- 4. Check and Install Dependencies ---
echo [INFO] Checking dependencies (requests, websocket-client, keyboard)...

"%PYTHON%" -c "import requests, websocket, keyboard" >nul 2>nul
if %errorlevel% neq 0 (
    echo [WARN] Missing dependencies. Installing...
    "%PYTHON%" -m pip install requests websocket-client keyboard
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b
    )
    echo [INFO] Dependencies installed successfully.
) else (
    echo [INFO] All dependencies are already installed.
)

:RUN
:: --- 5. Launch the Script ---
echo [INFO] Starting Run Button...
echo.
"%PYTHON%" float_run.py
pause
