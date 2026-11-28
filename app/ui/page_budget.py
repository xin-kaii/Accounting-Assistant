"""预算页（Owner: A｜第 9 天｜数据对接：A）

分工边界：
    - 进度条、颜色、告警区 = A
    - 预算存多少、花了多少、哪一档（ok/warn/over）= A（check_budget）
"""

from __future__ import annotations

import math
from datetime import date

import streamlit as st

from app.constants import CATEGORIES, LEVEL_OK, LEVEL_OVER, LEVEL_WARN
from app.services.budget import check_budget, delete_budget, set_budget

# 三档颜色，按 check_budget 返回的 level 上色
LEVEL_COLORS = {LEVEL_OK: "#2ecc71", LEVEL_WARN: "#f39c12", LEVEL_OVER: "#e74c3c"}
LEVEL_EMOJI = {LEVEL_OK: "🟢", LEVEL_WARN: "🟠", LEVEL_OVER: "🔴"}

TOTAL_BUDGET_LABEL = "总预算"  # 页面上这么说，存库时是 ''


def _month_options() -> list[str]:
    """从本月往前数 12 个月的 'YYYY-MM' 列表（本月排第一，作默认值）。"""
    today = date.today()
    options = []
    for offset in range(0, -12, -1):
        # 把"年-月"拍平成月序号再回退，12 月往前退一个月自动回到去年
        serial = today.year * 12 + (today.month - 1) + offset
        options.append(f"{serial // 12}-{serial % 12 + 1:02d}")
    return options


def _bar(ratio: float, color: str) -> None:
    """一根按 level 上色的进度条（HTML 版）。

    为什么不用 st.progress：streamlit 1.67 的 st.progress(value, text, width)
    **没有颜色参数**，颜色只能跟主题走，做不出"超支变红"。
    两层 div：外层灰底轨道，内层按百分比填色；宽度夹在 0~100%。
    """
    width_pct = max(0.0, min(ratio, 1.0)) * 100
    st.markdown(
        f'<div style="background:#e8e8e8;border-radius:999px;height:10px;">'
        f'<div style="background:{color};width:{width_pct:.0f}%;'
        f'height:10px;border-radius:999px;"></div></div>',
        unsafe_allow_html=True,
    )


def _render_budget_row(month: str, row: dict) -> None:
    """一根进度条 = 一条预算：名称 + 已花/上限/剩余 + 颜色条 + 删除按钮。"""
    name = row["category"] or TOTAL_BUDGET_LABEL
    level = row["level"]
    emoji = LEVEL_EMOJI[level]

    # ratio 可能是 inf（预算设了 0 元还花了钱），显示成 ∞，别让 f-string 打出 "inf%"
    if math.isinf(row["ratio"]):
        pct_text = "∞"
    else:
        pct_text = f"{row['ratio'] * 100:.0f}%"

    # 剩余为负时改说"超支"，比"剩余 ¥-12.00"直观
    if row["remain"] < 0:
        remain_text = f"超支 ¥{-row['remain']:,.2f}"
    else:
        remain_text = f"剩余 ¥{row['remain']:,.2f}"

    col_bar, col_del = st.columns([8, 1])
    with col_bar:
        st.markdown(
            f"{emoji} **{name}**　已花 **¥{row['spent']:,.2f}**"
            f" / 上限 ¥{row['budget']:,.2f}　{remain_text}（{pct_text}）"
        )
        _bar(row["ratio"], LEVEL_COLORS[level])
    with col_del:
        # key 必须唯一，不然 5 根条共用一个按钮状态会互相打架
        if st.button("删除", key=f"del-{month}-{row['category']}", width="stretch"):
            try:
                delete_budget(month, row["category"])
            except Exception as exc:
                st.error(f"删除失败（{type(exc).__name__}: {exc}）")
            else:
                st.rerun()  # 删完立刻重画，不然列表还留着刚删的那条


def render() -> None:
    """渲染预算页。

    1. 设置区：月份 + 类别（含"总预算"）+ 金额 -> set_budget()
    2. 展示区：每个预算一根进度条，显示 已花/上限/剩余
    3. 颜色按 level 上色：ok 绿、warn 橙、over 红
    4. 超支时顶部弹红色告警："餐饮已超支 15%"
    """
    st.subheader("预算管理")

    # 月份选择器放在表单外面：它同时驱动"设置区"和下面的"执行情况"，
    # 放进表单里就得点保存才生效，下面的进度条不会跟着切月份。
    month = st.selectbox("月份", _month_options())

    # ---------- 设置区 ----------
    with st.form("budget_form", border=True):
        st.write(f"给 **{month}** 设一个每月上限（重复保存同一个类别会覆盖旧的）")
        col_cat, col_amt = st.columns([2, 1])
        choice = col_cat.selectbox("类别", (TOTAL_BUDGET_LABEL, *CATEGORIES))
        amount = col_amt.number_input("每月上限（元）", min_value=0.0, step=100.0, format="%.2f")
        submitted = st.form_submit_button("保存预算", type="primary", width="stretch")

    if submitted:
        # 用 st.form 包起来：改下拉框、输金额不会每次都触发整页重跑，
        # 点"保存"才统一提交。类别选"总预算"时入库存 ''。
        category = "" if choice == TOTAL_BUDGET_LABEL else choice
        try:
            set_budget(month, float(amount), category)
            st.success(f"已保存：{month}「{choice}」上限 ¥{amount:,.2f}")
        except ValueError as e:
            st.error(f"没存进去：{e}")

    # ---------- 展示区 ----------
    st.divider()
    st.markdown(f"#### {month} 执行情况")

    try:
        rows = check_budget(month)
    except Exception as exc:      # 数据库被锁 / 预算表坏了，页面也不能红屏
        st.error(f"预算读取失败（{type(exc).__name__}: {exc}）")
        return
    if not rows:
        st.info("这个月还没设预算。用上面的表单加一条吧。")
        return

    # 超支告警集中放在最顶上，打开页面第一眼就能看到
    for row in rows:
        if row["level"] == LEVEL_OVER:
            name = row["category"] or TOTAL_BUDGET_LABEL
            st.error(f"🔴「{name}」已超支 ¥{-row['remain']:,.2f}（已用 {row['spent']:,.2f} / {row['budget']:,.2f}）")

    for row in rows:
        _render_budget_row(month, row)

    st.caption("🟢 已用 < 70%　🟠 70% ~ 100%（刚好 100% 算黄灯，不算超支）　🔴 > 100%")
