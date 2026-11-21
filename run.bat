@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM Keep this file ASCII-only. cmd.exe has a known bug parsing batch files
REM that contain non-ASCII bytes under "chcp 65001": it loses byte sync and
REM executes fragments of comments (e.g. a single CJK character) as commands.
REM All Chinese explanations belong in docs/, not in .bat comments.

if not exist ".venv\Scripts\python.exe" goto no_venv
if not exist ".env" copy ".env.example" ".env" >nul

REM Background job: wait until port 8501 is up, then let cmd open the browser.
REM Opening the browser must stay in cmd - Python's webbrowser can report
REM success while launching nothing (ShellExecute silent failure).
start "" /min cmd /c ".venv\Scripts\python.exe scripts\wait_for_port.py 8501 & start http://localhost:8501"

".venv\Scripts\python.exe" -m streamlit run app\ui\main.py --server.headless=true
exit /b 0

:no_venv
echo [ERROR] .venv not found
echo Run these commands first:
echo     python -m venv .venv
echo     .venv\Scripts\activate
echo     pip install -r requirements.lock.txt -i https://mirrors.aliyun.com/pypi/simple/
pause
exit /b 1
