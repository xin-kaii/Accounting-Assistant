@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto no_venv
if not exist ".env" copy ".env.example" ".env" >nul

rem 后台任务：先等端口就绪，再由 cmd 自己用 start 打开浏览器。
rem 打开浏览器的动作必须留在 cmd 里 —— Python 的 webbrowser 在部分机器上
rem 会报成功但实际不启动（ShellExecute 静默失败），cmd 的 start 更可靠。
start "" /min cmd /c ".venv\Scripts\python.exe scripts\wait_for_port.py 8501 & start http://localhost:8501"

".venv\Scripts\python.exe" -m streamlit run app\ui\main.py --server.headless=true
exit /b 0

:no_venv
echo [错误] 没有找到 .venv
echo 请先执行： python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.lock.txt -i https://mirrors.aliyun.com/pypi/simple/
pause
exit /b 1
