@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo       ComfyNode Sync - Launcher
echo ========================================================

echo 1. Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in system PATH! 
    echo Please install Python (Check "Add Python to PATH" during installation).
    pause
    exit /b
)

echo 2. Setting up environment...
set "RECREATE_VENV=0"

if exist "venv" (
    :: Check if venv is valid by trying to run its python
    venv\Scripts\python.exe --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo [WARN] Virtual environment seems broken or from another machine.
        echo [INFO] Recreating venv...
        set "RECREATE_VENV=1"
    ) else (
        echo [INFO] Existing venv is valid.
    )
) else (
    echo [INFO] venv not found. Creating new one...
    set "RECREATE_VENV=1"
)

if "!RECREATE_VENV!"=="1" (
    if exist "venv" (
        echo [INFO] Removing broken/old venv...
        rmdir /s /q "venv"
    )
    echo [INFO] Creating virtual environment...
    python -m venv venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b
    )
)

echo 3. Checking dependencies...
:: Always try to install/update dependencies to ensure consistency
echo [INFO] Installing/Updating dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b
)

echo 4. Starting GUI...
echo.
start "" /B venv\Scripts\pythonw.exe gui.py
exit
