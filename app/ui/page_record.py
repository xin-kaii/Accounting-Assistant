"""记账页（Owner: C｜第 3-4 天｜数据对接：B）

页面流程（这也是答辩会被问的那道题，要能讲清楚）：
    1. 用户在输入框打"午饭 25，和同事 AA"
    2. 点"解析" -> 调 B 的 parse_record(text)
    3. 屏幕上出现一张确认卡片，显示 金额 / 类别 / 时间 / 商户
    4. 用户在卡片里可以改任何一项
    5. 点"确认记账" -> 调 A 的 add_transaction(record)
    6. 提示"已记上"，清空输入框
    7. 如果 B 返回的 missing_fields 非空 -> 卡片上显示追问，不让直接确认

分工边界：
    - 卡片长什么样、按钮放哪、布局怎么排 = C
    - 卡片里每个字段显示什么、缺字段时提示什么 = B
"""

from __future__ import annotations

import streamlit as st


def render() -> None:
    """渲染记账页。TODO(C) 第 3-4 天"""
    st.subheader("一句话记账")
    st.info(
        "TODO(C) 第 3-4 天：\n"
        "1. 输入框 + 『解析』按钮\n"
        "2. 确认卡片（金额/类别/时间/商户可编辑）\n"
        "3. 『确认记账』按钮 -> A 的 add_transaction()\n"
        "4. missing_fields 非空时显示追问"
    )


def render_confirm_card(record: dict) -> dict | None:
    """把 B 返回的 record 渲染成可编辑的确认卡片，返回用户改完后的 record。

    这个函数是 C 和 B 的交界：
    - C 负责控件和布局
    - B 负责告诉 C：哪些字段要显示、missing_fields 里有什么、怎么提示

    TODO(C) 第 3-4 天，和 B 一起写
    """
    raise NotImplementedError("TODO(C) 第 3-4 天")
