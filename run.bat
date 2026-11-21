@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo    记账助手 - 本地启动
echo ============================================
echo.

if not exist ".venv\Scripts\python.exe" goto no_venv
if not exist ".env" goto no_env
goto run

:no_venv
echo [错误] 没有找到虚拟环境 .venv
echo.
echo 请先在本目录依次执行：
echo     python -m venv .venv
echo     .venv\Scripts\activate
echo     pip install -r requirements.lock.txt -i https://mirrors.aliyun.com/pypi/simple/
echo.
pause
exit /b 1

:no_env
echo [提示] 没有 .env，已从 .env.example 复制一份
echo        没有 API Key 也能启动，AI 功能会走离线模式
copy ".env.example" ".env" >nul
echo.

:run
echo 正在启动，浏览器会自动打开 http://localhost:8501
echo 停止服务请按 Ctrl+C
echo.
".venv\Scripts\python.exe" -m streamlit run app\ui\main.py
echo.
echo 服务已停止。
pause
