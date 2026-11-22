@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM Keep this file ASCII-only (see run.bat comment): cmd.exe mis-parses
REM non-ASCII bytes in .bat files when the active code page is 65001.

if not exist ".venv\Scripts\python.exe" goto no_venv

".venv\Scripts\python.exe" scripts\generate_sample_data.py %*

echo.
echo [DONE] data\sample_transactions.csv
pause
exit /b 0

:no_venv
echo [ERROR] .venv not found - create it first, see README
pause
exit /b 1
