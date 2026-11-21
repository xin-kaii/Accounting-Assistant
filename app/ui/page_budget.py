"""预算页（Owner: D｜第 9 天｜数据对接：A）

分工边界：
    - 进度条、颜色、告警区 = D
    - 预算存多少、花了多少、哪一档（ok/warn/over）= A（check_budget）
"""

from __future__ import annotations

import streamlit as st

# 三档颜色，D 用 st.progress 或 plotly 时按这个上色
LEVEL_COLORS = {"ok": "green", "warn": "orange", "over": "red"}


def render() -> None:
    """渲染预算页。TODO(D) 第 9 天

    要求：
    1. 设置区：月份 + 类别（含"总预算"）+ 金额 -> A 的 set_budget()
    2. 展示区：每个预算一根进度条，显示 已花/上限/剩余
    3. 颜色按 A 返回的 level 上色：ok 绿、warn 橙、over 红
    4. 超支时顶部弹红色告警："餐饮已超支 15%"
    """
    st.subheader("预算管理")
    st.info(
        "TODO(D) 第 9 天：\n"
        "设置预算 -> A 的 set_budget() ；展示进度条 -> A 的 check_budget()"
    )
