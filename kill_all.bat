@echo off
echo Killing all running run_button instances...

:: 1. Kill python processes running float_run.py
wmic process where "CommandLine like '%%float_run.py%%'" call terminate >nul 2>nul

echo.
echo All instances should be closed now.
pause