"""统计页（Owner: A｜第 7-8 天｜数据对接：A）

分工边界：
    - 图放哪、用什么图、怎么切换 = A
    - 数字怎么算、返回什么结构 = A（get_stats）
    A 不自己算任何数，只负责把 A 返回的 by_category / monthly_trend 画出来。
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

import plotly.express as px
import streamlit as st

from app.services.stats import get_stats


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    """某个月的第一天和最后一天。monthrange(year, month)[1] = 该月天数。"""
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def render() -> None:
    """渲染统计页。

    1. 顶部三个指标卡：本月支出总额 / 笔数 / 单笔最高
    2. 饼图：分类占比（数据来自 get_stats()["by_category"]）
    3. 折线图：月度趋势（数据来自 get_stats()["monthly_trend"]）
    4. 时间切换：本月 / 上月 / 今年
    """
    st.subheader("消费统计")

    # ---------- 时间切换：决定指标卡和饼图看哪一段 ----------
    today = date.today()
    period = st.radio("时间范围", ["本月", "上月", "今年"], horizontal=True)
    if period == "本月":
        start, end = _month_bounds(today.year, today.month)
    elif period == "上月":
        # 本月 1 号往前退一天，落到的那个月就是上月——不用自己写"12 月回去年"
        first_of_prev = date(today.year, today.month, 1) - timedelta(days=1)
        start, end = _month_bounds(first_of_prev.year, first_of_prev.month)
    else:  # 今年
        start, end = date(today.year, 1, 1), today

    try:
        stats = get_stats(str(start), str(end))
    except Exception as exc:      # 数据库被锁 / 日期非法，都不能让页面红屏
        st.error(f"统计失败（{type(exc).__name__}: {exc}）")
        return

    # ---------- 顶部三个指标卡 ----------
    col_total, col_count, col_max = st.columns(3)
    col_total.metric(f"{period}支出", f"¥{stats['total']:,.2f}")
    col_count.metric("笔数", f"{stats['count']} 笔")
    if stats["max_single"]:
        merchant = stats["max_single"]["merchant"] or "未知商户"
        col_max.metric(
            "单笔最高",
            f"¥{stats['max_single']['amount']:,.2f}",
            help=f"{merchant} · {stats['max_single']['occurred_at']}",
        )
    else:
        col_max.metric("单笔最高", "—")

    # ---------- 饼图：分类占比 ----------
    st.divider()
    if stats["by_category"]:
        fig = px.pie(
            names=[row["category"] for row in stats["by_category"]],
            values=[row["amount"] for row in stats["by_category"]],
            hole=0.45,  # 环形图，比实心饼好看一点，中间留白还能放总额
        )
        fig.update_traces(textinfo="percent+label")
        st.plotly_chart(fig, width="stretch")
    else:
        st.info(f"{period}还没有支出记录，去「✍️ 记账」页记一笔吧～")

    # ---------- 折线图：月度趋势 ----------
    st.divider()
    st.markdown(f"#### {today.year} 年月度趋势")

    # 趋势固定看"今年 1 月至今"，不跟着上面的切换变：
    # 选"本月"时区间里只有一个月，折线图只剩一个点，画不出"趋势"。
    try:
        trend = get_stats(f"{today.year}-01-01", str(today))
    except Exception as exc:
        st.warning(f"月度趋势查不出来（{type(exc).__name__}: {exc}）")
        return
    by_month = {row["month"]: row["amount"] for row in trend["monthly_trend"]}

    # GROUP BY 只会给"有支出"的月份，没花的月份要自己补 0，
    # 否则折线会把 3 月直接连到 5 月，看起来像没花钱的那个月不存在。
    months_axis = []
    amounts = []
    for m in range(1, today.month + 1):
        key = f"{today.year}-{m:02d}"
        months_axis.append(key)
        amounts.append(by_month.get(key, 0.0))

    if any(amounts):
        fig = px.line(
            x=months_axis,
            y=amounts,
            markers=True,  # 每个月一个圆点，一个月 25 块也看得见
            labels={"x": "月份", "y": "支出（元）"},
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("今年还没有支出数据。")
