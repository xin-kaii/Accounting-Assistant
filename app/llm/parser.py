"""记账解析：一句话 -> 一笔账（Owner: B｜第 5-6 天完成）

这是 B 对外最重要的一个函数，C 的记账页都调它。
"""

from __future__ import annotations

from datetime import datetime

from app import config
from app.constants import CATEGORIES, DEFAULT_CATEGORY, DIRECTION_EXPENSE, DIRECTIONS
from app.llm import client, mock_llm, prompts


def _normalize_record(raw: dict) -> dict:
    """把模型返回的 dict 规整成 9 个字段，缺什么补什么。

    模型可能返回：字符串金额、负数、非法类别、缺失字段；
    这里统一清洗，保证页面拿到的结构永远一致。
    """
    now_str = datetime.now().strftime("%Y-%m-%d 00:00:00")

    # amount：只认数字；非数字或空 -> None；负数取绝对值（方向由 direction 表达）
    amount_raw = raw.get("amount")
    amount = None
    if amount_raw is not None and str(amount_raw).strip() != "":
        try:
            amount = round(float(amount_raw), 2)
            if amount < 0:
                amount = abs(amount)
        except (TypeError, ValueError):
            amount = None

    # direction：只认 income/expense，其他一律按支出
    direction = raw.get("direction")
    direction = direction if direction in DIRECTIONS else DIRECTION_EXPENSE

    # category：必须属于 10 类，否则兜底
    category = raw.get("category")
    category = category if category in CATEGORIES else DEFAULT_CATEGORY

    def _str_or_none(value):
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None

    subcategory = _str_or_none(raw.get("subcategory"))
    merchant = _str_or_none(raw.get("merchant"))
    note = _str_or_none(raw.get("note"))
    occurred_at = _str_or_none(raw.get("occurred_at")) or now_str

    # confidence：0-1 小数，非法值给 0.5
    try:
        confidence = float(raw.get("confidence"))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    # missing_fields：必须是字符串列表；金额缺失时补 amount
    missing = raw.get("missing_fields")
    if not isinstance(missing, list):
        missing = []
    missing = [str(x) for x in missing if isinstance(x, str)]
    if amount is None and "amount" not in missing:
        missing.append("amount")

    return {
        "amount": amount,
        "direction": direction,
        "category": category,
        "subcategory": subcategory,
        "merchant": merchant,
        "note": note,
        "occurred_at": occurred_at,
        "confidence": confidence,
        "missing_fields": missing,
    }


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

    实现见下方。
    """
    if config.llm_ready():
        try:
            raw = client.chat_json(prompts.SYSTEM_PARSE_RECORD, text)
            return _normalize_record(raw)
        except client.LLMError:
            # 真模型不可用（没网/超时/解析失败）就退回离线规则，保证演示不翻车
            return mock_llm.parse_record(text)
    return mock_llm.parse_record(text)


def parse_multiple(text: str) -> list[dict]:
    """一条消息里有多笔账时用（例："打车32，午饭25"）。

    返回 list[dict]，每项结构和 parse_record 一样。
    做不完可以不做，先把单笔跑通。

    TODO(B) 加分项
    """
    raise NotImplementedError("TODO(B) 加分项，可跳过")
