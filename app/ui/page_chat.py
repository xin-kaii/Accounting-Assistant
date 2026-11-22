"""对话页 / 自然语言查账（Owner: B｜第 9-10 天｜数据对接：B）

分工边界：
    - 消息气泡、输入框、历史记录 = B
    - 问题怎么解析成查询条件、结果怎么组织成一句话 = B
    - 数字本身来自 A 的 SQL，不许由模型生成（这一点答辩会问）
"""

from __future__ import annotations

import streamlit as st


def render() -> None:
    """渲染对话页。TODO(B) 第 9-10 天

    要求：
    1. 下面一个输入框，上面是消息历史（用 st.session_state 存历史，
       但⚠️ 账单数据不能存在 session_state 里，必须落库）
    2. 用户提问 -> B 的 parse_query() -> A 的 get_stats() -> 拼成中文回复
    3. 解析失败时提示"没听懂，试试『上个月吃饭花了多少』"，不要崩
    4. 可以给三个示例问题按钮，方便评审现场点（演示友好）
    """
    st.subheader("用一句话问账")
    st.info(
        "TODO(B) 第 9-10 天：\n"
        "输入问题 -> B 的 parse_query() -> A 的 get_stats() -> 中文回复\n"
        "示例问题按钮：『上个月吃饭花了多少』『这个月哪类花得最多』"
    )
