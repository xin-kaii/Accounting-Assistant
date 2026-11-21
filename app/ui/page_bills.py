"""账单列表页（Owner: D｜第 5-6 天）

直接调 A 的 list_transactions()，没有跨人依赖，D 可以自己一个人做完。
"""

from __future__ import annotations

import streamlit as st


def render() -> None:
    """渲染账单列表。TODO(D) 第 5-6 天

    要求：
    1. 筛选器：时间范围（本月/上月/自定义）、类别下拉、收支切换
    2. 按日期分组显示，每组显示当天小计
    3. 每行可以编辑 / 删除（调 A 的 update_transaction / delete_transaction）
    4. 空数据时显示"还没有账单，去记账页试试"
    """
    st.subheader("账单列表")
    st.info(
        "TODO(D) 第 5-6 天：\n"
        "筛选器（时间/类别/收支）-> A 的 list_transactions() -> 按天分组表格"
    )
