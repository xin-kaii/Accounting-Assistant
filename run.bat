@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto no_venv
if not exist ".env" copy ".env.example" ".env" >nul

rem 后台轮询端口，服务一就绪就打开浏览器（不等固定秒数）
start "" /b ".venv\Scripts\python.exe" scripts\open_when_ready.py 8501

".venv\Scripts\python.exe" -m streamlit run app\ui\main.py --server.headless=true
exit /b 0

:no_venv
echo [错误] 没有找到 .venv
echo 请先执行： python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.lock.txt -i https://mirrors.aliyun.com/pypi/simple/
pause
exit /b 1
