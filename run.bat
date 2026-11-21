@echo off
chcp 65001 >nul
REM 一键启动（Windows）。双击即可，或者在终端里运行 run.bat
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 没找到虚拟环境 .venv
    echo 先执行：
    echo     python -m venv .venv
    echo     .venv\Scripts\activate
    echo     pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist ".env" (
    echo [提示] 没有 .env，正在从 .env.example 复制一份，记得填 API Key
    copy ".env.example" ".env" >nul
)

.venv\Scripts\python.exe -m streamlit run app\ui\main.py
pause
