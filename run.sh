#!/usr/bin/env bash
# 一键启动（macOS / Linux）。用法：bash run.sh
set -e
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "[错误] 没找到虚拟环境 .venv"
    echo "先执行："
    echo "    python3 -m venv .venv"
    echo "    source .venv/bin/activate"
    echo "    pip install -r requirements.lock.txt"
    echo "    （网络慢可加镜像源：-i https://mirrors.aliyun.com/pypi/simple/）"
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "[提示] 没有 .env，正在从 .env.example 复制一份，记得填 API Key"
    cp .env.example .env
fi

exec .venv/bin/python -m streamlit run app/ui/main.py
