"""统计页（Owner: D｜第 7-8 天｜数据对接：A）

分工边界：
    - 图放哪、用什么图、怎么切换 = D
    - 数字怎么算、返回什么结构 = A（get_stats）
    D 不自己算任何数，只负责把 A 返回的 by_category / monthly_trend 画出来。
"""

from __future__ import annotations

import streamlit as st


def render() -> None:
    """渲染统计页。TODO(D) 第 7-8 天

    要求：
    1. 顶部三个指标卡：本月支出总额 / 笔数 / 单笔最高
    2. 饼图：分类占比（用 plotly，数据来自 get_stats()["by_category"]）
    3. 折线图：月度趋势（数据来自 get_stats()["monthly_trend"]）
    4. 时间切换：本月 / 上月 / 今年
    """
    st.subheader("消费统计")
    st.info(
        "TODO(D) 第 7-8 天：\n"
        "三个指标卡 + 分类饼图 + 月度折线图，数据全部来自 A 的 get_stats()"
    )
