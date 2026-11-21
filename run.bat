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
echo 地址： http://localhost:8501
echo 停止： 在这个窗口按 Ctrl+C
echo.
echo 正在启动，约 5 秒后会自动打开浏览器...
echo 如果没打开，把上面那个地址复制到浏览器里就行。
echo.

rem 后台延迟 6 秒再开浏览器：不依赖 Streamlit 自己弹窗口，
rem 避免浏览器权限冲突（比如 Edge 提示"现有实例以提升的权限运行"）。
start "" /min cmd /c "timeout /t 6 /nobreak >nul & start http://localhost:8501"

".venv\Scripts\python.exe" -m streamlit run app\ui\main.py --server.headless=true

echo.
echo 服务已停止。
pause
