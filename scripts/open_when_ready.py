"""端口就绪后立刻打开浏览器（run.bat 调用，也可以单独跑）

为什么不让 Streamlit 自己开浏览器：
  1. 它会撞上浏览器的权限问题（Windows 上常见：Edge 提示
     「现有实例正在以提升的权限运行」），撞完就静默失败；
  2. 它只能固定等几秒，机器快慢不同，要么白等要么抢跑。

这个脚本换成轮询端口：服务一就绪马上打开，通常 1~2 秒。

用法：
    python scripts/open_when_ready.py 8501
    python scripts/open_when_ready.py 8501 --no-open   # 只等，不开浏览器（测试用）
"""

from __future__ import annotations

import socket
import sys
import time
import webbrowser

TIMEOUT_SECONDS = 30.0
POLL_INTERVAL = 0.15


def wait_for_port(port: int, timeout: float = TIMEOUT_SECONDS) -> bool:
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
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    port = int(args[0]) if args else 8501
    url = f"http://localhost:{port}"

    if not wait_for_port(port):
        # 超时不弹任何东西：服务没起来时，用户更该看的是 Streamlit 的报错
        return 0

    if "--no-open" not in sys.argv:
        webbrowser.open(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
