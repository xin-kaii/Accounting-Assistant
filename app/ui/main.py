"""Streamlit 入口（Owner: A）

启动：streamlit run app/ui/main.py
5 个页面在这里组装，每个页面的实现放在同目录的 page_*.py。

⚠️ 为什么开头要动 sys.path：
   streamlit 把"脚本所在目录"加进 sys.path，不是项目根目录。
   不加这段，从任意位置启动都会报 No module named 'app'。
   这是零基础最常踩的坑之一，已经在骨架里处理掉了。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 把项目根目录加进 import 路径（必须在 import app.* 之前）
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app.config import llm_ready, vlm_ready  # noqa: E402
from app.services.ledger import count_transactions  # noqa: E402
from app.ui.page_bills import render as render_bills  # noqa: E402
from app.ui.page_budget import render as render_budget  # noqa: E402
from app.ui.page_chat import render as render_chat  # noqa: E402
from app.ui.page_record import render as render_record  # noqa: E402
from app.ui.page_stats import render as render_stats  # noqa: E402

st.set_page_config(page_title="记账助手", page_icon="💰", layout="wide")

# ---------- 侧边栏 ----------
with st.sidebar:
    st.title("💰 记账助手")
    st.caption("2026 GDUF · 方向一 · 选题 A")
    st.divider()

    # 数据与模型状态（A）
    try:
        st.caption(f"📒 已记账 {count_transactions()} 笔")
    except Exception:
        # 全新克隆还没跑 init_db（data/ 里只有 .gitkeep），侧边栏不能崩
        st.caption("📒 数据库还没初始化")

    llm_ok = llm_ready()
    st.caption(f"{'✅' if llm_ok else '⚪'} 文本模型：{'已配置' if llm_ok else '未配置（走离线兜底）'}")
    vlm_ok = vlm_ready()
    st.caption(f"{'✅' if vlm_ok else '⚪'} 视觉模型：{'已配置' if vlm_ok else '未配置（图片识别不可用）'}")

    st.divider()
    st.caption("团队：A 数据+统计预算页 / B AI+对话页 / C 图片+记账账单页")

# ---------- 5 个页面 ----------
tab_record, tab_bills, tab_stats, tab_budget, tab_chat = st.tabs(
    ["✍️ 记账", "📋 账单", "📊 统计", "🎯 预算", "💬 问账"]
)

with tab_record:
    render_record()

with tab_bills:
    render_bills()

with tab_stats:
    render_stats()

with tab_budget:
    render_budget()

with tab_chat:
    render_chat()
