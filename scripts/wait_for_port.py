"""等待 Streamlit 端口就绪（run.bat 调用）

只做一件事：轮询 127.0.0.1:8501，端口一就绪就退出。
浏览器由 run.bat 里的 cmd `start` 打开，这个脚本不碰浏览器。

为什么把"开浏览器"交给 cmd 而不是 Python：
- 实测在这台机器上 Python 的 webbrowser（走 os.startfile / ShellExecute）、
  以及直接调 msedge.exe，都可能"报成功但什么都没起"；
- 而 cmd 的 start 命令是另一条执行路径，在用户机器上验证过可用。

为什么不固定 sleep 几秒：
机器快慢不同。轮询端口能在服务真正就绪的瞬间返回，
通常 1~2 秒，比死等 6 秒快，也不会抢跑。

用法：
    python scripts/wait_for_port.py 8501
    python scripts/wait_for_port.py 8501 --timeout 15
"""

from __future__ import annotations

import argparse
import socket
import time

POLL_INTERVAL = 0.15


def wait_for_port(port: int, timeout: float) -> bool:
    """等某个本地端口开始监听。成功返回 True，超时返回 False。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(POLL_INTERVAL)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="等待端口就绪")
    parser.add_argument("port", nargs="?", type=int, default=8501)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    wait_for_port(args.port, args.timeout)
    # 不管成没成都以 0 退出：由 run.bat 决定要不要打开浏览器。
    # 服务没起来时，用户更该看到的是 Streamlit 自己的报错。
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
