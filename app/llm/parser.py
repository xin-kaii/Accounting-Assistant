"""记账解析：一句话 -> 一笔账（Owner: B｜第 5-6 天完成）

这是 B 对外最重要的一个函数，C 的记账页都调它。
"""

from __future__ import annotations

from app import config
from app.llm import client, mock_llm, prompts


def parse_record(text: str) -> dict:
    """把用户一句话解析成标准账单数据。

    返回（任何情况下都返回这个结构，字段一个不少）：
    {
        "amount": 25.0 或 None,          # 单位：元（如"午饭 25"就是 25.0，不是 2500）
        "direction": "expense",
        "category": "餐饮",
        "subcategory": None,
        "merchant": None,
        "note": "和同事 AA",
        "occurred_at": "2026-11-20 12:00:00",
        "confidence": 0.93,
        "missing_fields": [],        # 非空时 C 的页面要显示追问
    }

    两条路径，B 必须都实现：
    1. config.llm_ready() 为 True  -> 调 client.chat_json(prompts.SYSTEM_PARSE_RECORD, text)
    2. 否则或抛出 LLMError        -> 退回 mock_llm.parse_record(text)

    ⚠️ 无论走哪条路，返回结构必须完全一样。页面只认这一套字段。

    TODO(B) 第 5-6 天
    """
    raise NotImplementedError("TODO(B) 第 5-6 天")


def parse_multiple(text: str) -> list[dict]:
    """一条消息里有多笔账时用（例："打车32，午饭25"）。

    返回 list[dict]，每项结构和 parse_record 一样。
    做不完可以不做，先把单笔跑通。

    TODO(B) 加分项
    """
    raise NotImplementedError("TODO(B) 加分项，可跳过")
