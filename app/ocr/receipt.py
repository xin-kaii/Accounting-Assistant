"""小票 / 支付截图识别（Owner: C｜第 5-6 天完成，第 3-4 天先把骨架立起来）

思路：**不自己写 OCR**。直接把图片丢给视觉大模型，让它返回 JSON。
     不用 Tesseract、不用 OpenCV 预处理、不用训练。

为什么这么做（答辩必答）：
  中文小票版式乱、字体杂、还有手写，传统 OCR 抽字段的准确率撑不住演示；
  视觉模型一次调用就能出结构化结果，成本几毛钱，省下至少 3 天。

和 B 的分工：
  返回结构和 parse_record() **完全一致**，页面才能复用同一张确认卡片。
  调模型的部分我直接写在 _ask_vision() 里（openai SDK 兼容各家）；
  B 的 client.chat_vision() 写好以后，可以把 _ask_vision() 换成它，其余不用动。
"""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime

from app import config
from app.constants import (
    CATEGORIES,
    DEFAULT_CATEGORY,
    DIRECTION_EXPENSE,
    DIRECTION_INCOME,
    DIRECTIONS,
)
from app.db.conn import DATETIME_FMT

# 支持的图片格式，D 的上传控件要用它做校验
ALLOWED_TYPES = ("image/jpeg", "image/png", "image/webp")
MAX_SIZE_MB = 5

# 置信度低于这个值，页面必须强制用户人工确认
LOW_CONFIDENCE = 0.6


class ReceiptError(ValueError):
    """识别失败（格式不支持、没配 Key、模型没认出是账单……）。

    继承 ValueError：页面用 `except ValueError` 就能接住，
    同时报错信息是给用户看的中文，不是一串 traceback。
    """


SYSTEM_PROMPT_RECEIPT = f"""你是小票/支付截图识别助手。用户会给你一张图，
你要读出这张图里的一笔消费，输出 JSON。

【输出要求】只输出一个 JSON 对象，不要解释文字，不要 markdown 代码块：
{{
  "is_receipt": 布尔，这张图是不是小票/支付截图/账单。不是的话后面字段随便填、confidence 填 0,
  "amount": 数字，**这笔消费的总额**，单位元。认不出就填 null,
  "direction": "expense" 或 "income"，默认 "expense",
  "category": 从这些里选一个：{"、".join(CATEGORIES)}。判断不了填 "其他",
  "subcategory": 更细的分类，可为 null,
  "merchant": 商户名，可为 null,
  "note": 备注，可为 null,
  "occurred_at": "YYYY-MM-DD HH:MM:SS"，小票上的消费时间。没有就填 null,
  "confidence": 0 到 1 的小数，你对这次识别的把握,
  "missing_fields": 字符串数组，没认出来的字段名（如 ["amount"]），全认出来就是 [],
  "raw_text": 图上看到的关键文字（店名、合计、时间），给用户核对用
}}

【铁律】
- 一张小票上有多个商品明细时，**只取这一笔的最终支付金额**，不要逐条列出
- 金额优先级：**实付 / 支付金额 / 优惠后金额 > 合计 > 总价**。
  图上同时出现"总价"和"实付"时，一律取"实付"（用户真正花掉的钱）
- 金额必须是图上真实印着的数字，看不清就填 null 放进 missing_fields，**绝对不许猜**
- 时间只取小票上的，没有就 null，不要用"今天"顶替
- 图不是小票（自拍、风景、聊天截图）就把 is_receipt 填 false
"""


# ============================================================
# 一、调视觉模型
# ============================================================

def _image_data_uri(image_bytes: bytes, mime_type: str) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"


def _extract_json(text: str) -> dict:
    """从模型回复里抠出 JSON。

    模型经常不听话：包 ```json 代码块、前面加一句"好的，这是结果"。
    先直接 loads，失败再抠第一个 { 到最后一个 }，两次都失败就抛 ReceiptError。
    """
    text = (text or "").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise ReceiptError("视觉模型返回的不是 JSON，没法解析") from None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            raise ReceiptError("视觉模型返回的 JSON 坏了，没法解析") from None
    if not isinstance(data, dict):
        raise ReceiptError("视觉模型返回的不是一个 JSON 对象")
    return data


def _looks_like_placeholder(api_key: str) -> bool:
    """判断 Key 是不是 .env.example 里抄下来的占位符。

    为什么单独判：占位符（比如中文的"你的key"）不会让"有没有配 Key"的判断为假，
    但一调就会抛 UnicodeEncodeError（HTTP header 只能放 ASCII），
    报错看不懂、还很难查。提前拦下来，给一句人话。
    """
    if not api_key:
        return True
    if not api_key.isascii():          # 中文占位符，最典型
        return True
    return len(api_key) < 16          # 真实 Key 都远长于 16 位


def _ask_vision(image_bytes: bytes, mime_type: str) -> dict:
    """把图片丢给视觉模型，拿回一个 dict。

    ⚠️ 这里没有做"重试 1 次"的完整策略（那是 B 的 client 负责的事），
       只保证：失败时抛 ReceiptError，**绝不让页面卡死或崩**。
    """
    if not config.vlm_ready() or _looks_like_placeholder(config.VLM_API_KEY):
        raise ReceiptError(
            "视觉模型的 Key 还没填好：请在 .env 里把 VLM_API_KEY 换成真实 Key"
            "（现在还是『你的key』这种占位符）。没 Key 也能演示——上传会提示这句，不会崩。"
        )

    try:
        from openai import OpenAI
    except ImportError:  # pragma: no cover - requirements.txt 里已经钉了 openai
        raise ReceiptError("没装 openai 库，先 pip install -r requirements.txt") from None

    client = OpenAI(base_url=config.VLM_BASE_URL, api_key=config.VLM_API_KEY, timeout=60.0)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_RECEIPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "识别这张小票，按要求的 JSON 输出。"},
                {"type": "image_url", "image_url": {"url": _image_data_uri(image_bytes, mime_type)}},
            ],
        },
    ]

    try:
        resp = client.chat.completions.create(model=config.VLM_MODEL, messages=messages)
    except Exception as exc:  # 网络、超时、401、额度用完……
        raise ReceiptError(f"视觉模型调用失败（{type(exc).__name__}: {exc}）") from exc

    content = (resp.choices[0].message.content or "").strip()
    return _extract_json(content)


# ============================================================
# 二、把模型返回的东西整理成和 parse_record 一样的结构
# ============================================================

def _to_amount(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = re.sub(r"[^\d.]", "", value)
        if not value:
            return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, 2) if number > 0 else None


def _to_datetime(value) -> str:
    """小票上的时间写法五花八门，统一成 'YYYY-MM-DD HH:MM:SS'。"""
    if isinstance(value, datetime):
        return value.strftime(DATETIME_FMT)
    raw = str(value or "").strip()
    for fmt in (DATETIME_FMT, "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d",
                "%Y年%m月%d日 %H:%M", "%Y年%m月%d日"):
        try:
            return datetime.strptime(raw, fmt).strftime(DATETIME_FMT)
        except ValueError:
            continue
    return ""   # 空字符串 = 模型没给时间，由下面统一兜底


def _normalize(raw: dict) -> dict:
    """字段补全 + 校验。**页面只认这个结构**。"""
    amount = _to_amount(raw.get("amount"))
    category = raw.get("category")
    if category not in CATEGORIES:
        category = DEFAULT_CATEGORY
    direction = raw.get("direction")
    if direction not in DIRECTIONS:
        direction = DIRECTION_EXPENSE

    occurred_at = _to_datetime(raw.get("occurred_at"))
    confidence = raw.get("confidence")
    confident = isinstance(confidence, (int, float))
    confidence = min(max(float(confidence), 0.0), 1.0) if confident else 0.5

    missing = [str(f) for f in (raw.get("missing_fields") or []) if str(f)]
    if amount is None and "amount" not in missing:
        missing.append("amount")
    if amount is not None and "amount" in missing:
        missing.remove("amount")

    # 没认出时间：用今天顶，但置信度打对折（答辩会问这一条）
    if not occurred_at:
        occurred_at = datetime.now().strftime(DATETIME_FMT)
        confidence *= 0.5

    return {
        "amount": amount,
        "direction": direction,
        "category": category,
        "subcategory": raw.get("subcategory") or None,
        "merchant": raw.get("merchant") or None,
        "note": raw.get("note") or None,
        "occurred_at": occurred_at,
        "confidence": round(confidence, 2),
        "missing_fields": missing,
        "raw_text": raw.get("raw_text") or "",
    }


# ============================================================
# 三、对外两个函数
# ============================================================

# ============================================================
# 三、金额兜底：外卖/支付截图上的"实付"比"总价"更该记
# ============================================================

# 为什么要有这段：prompt 里写了"实付优先"，模型照样会取"总价"（实测过一次）。
# 金额是纯数字，正则比模型靠得住——这是全项目反复用的一条经验。
_PAYMENT_HINTS = ("实付", "支付金额", "实收", "订单金额")
_PAYMENT_RE = re.compile(
    r"(实付|支付金额|实收|订单金额)[^0-9]{0,20}?(\d+(?:\.\d{1,2})?)"
)


def _fix_amount_with_text(result: dict) -> dict:
    """模型把"总价"当金额时，用 raw_text 里的"实付"把它掰回来。"""
    text = result.get("raw_text") or ""
    match = _PAYMENT_RE.search(text)
    if not match:
        return result

    paid = _to_amount(match.group(2))
    if paid is None or result.get("amount") is None:
        return result
    if abs(paid - result["amount"]) < 0.01:
        return result

    result["amount"] = paid
    result["note"] = (result.get("note") or "") or "已按『实付』金额记账"
    return result


def extract_receipt(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """图片 -> 标准账单数据（字段和 B 的 parse_record 完全一致）。

    返回：
    {
        "amount": 25.0 或 None,          # 单位：元（和 parse_record 保持一致，不是分）
        "direction": "expense",
        "category": "餐饮",
        "subcategory": None,
        "merchant": "沙县小吃",
        "note": None,
        "occurred_at": "2026-11-20 12:30:00",
        "confidence": 0.85,
        "missing_fields": [],
        "raw_text": "识别到的原始文字，给用户看个依据",
    }

    raise ReceiptError（= ValueError）：格式不支持 / 超过 5MB / 没配 Key /
        模型调用失败 / 完全没认出来

    必须处理的四种情况（答辩会问）：
    1. 金额是 0 或没认出来 -> amount=None，missing_fields 加 "amount"
    2. 没有日期 -> 用今天，confidence 打 0.5 折
    3. 是多笔明细（一张小票买了 5 样东西）-> 只取总额，不拆
    4. 图片不是小票（比如一张自拍）-> raise ValueError("没看出这是账单")
    """
    if not image_bytes:
        raise ReceiptError("没收到图片内容，请重新上传")
    if len(image_bytes) > MAX_SIZE_MB * 1024 * 1024:
        raise ReceiptError(f"图片超过 {MAX_SIZE_MB}MB，请压缩后再上传")
    if mime_type not in ALLOWED_TYPES:
        raise ReceiptError(f"不支持的图片格式：{mime_type}（只支持 JPG / PNG / WEBP）")

    raw = _ask_vision(image_bytes, mime_type)

    # 第 4 种情况：模型自己说"这不是小票"
    if raw.get("is_receipt") is False:
        raise ReceiptError("没看出这是账单：请上传小票或支付截图")

    result = _normalize(raw)
    result = _fix_amount_with_text(result)

    # 双保险：模型没说不是小票，但金额、商户、原文全空 -> 等于没认出来
    if result["amount"] is None and not result["merchant"] and not result["raw_text"]:
        raise ReceiptError("没看出这是账单：请上传小票或支付截图")

    return result


def needs_manual_review(result: dict) -> bool:
    """要不要强制走人工确认。

    规则：confidence 低于 LOW_CONFIDENCE，或 missing_fields 非空 -> True
    页面据此决定"能不能直接入库"还是"必须先让用户改一遍"。
    """
    if not isinstance(result, dict):
        return True
    confidence = result.get("confidence")
    if not isinstance(confidence, (int, float)) or confidence < LOW_CONFIDENCE:
        return True
    return bool(result.get("missing_fields"))
