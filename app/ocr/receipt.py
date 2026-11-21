"""小票 / 支付截图识别（Owner: C｜第 5-6 天完成）

思路：**不自己写 OCR**。直接把图片丢给视觉大模型，让它返回 JSON。
     不用 Tesseract、不用 OpenCV 预处理、不用训练。

为什么这么做（答辩必答）：
  中文小票版式乱、字体杂、还有手写，传统 OCR 抽字段的准确率撑不住演示；
  视觉模型一次调用就能出结构化结果，成本几毛钱，省下至少 3 天。
"""

from __future__ import annotations

# 支持的图片格式，D 的上传控件要用它做校验
ALLOWED_TYPES = ("image/jpeg", "image/png", "image/webp")
MAX_SIZE_MB = 5

# 置信度低于这个值，页面必须强制用户人工确认
LOW_CONFIDENCE = 0.6


def extract_receipt(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """图片 -> 标准账单数据（字段和 B 的 parse_record 完全一致）。

    返回：
    {
        "amount": 25.0 或 None,
        "direction": "expense",
        "category": "餐饮",
        "merchant": "沙县小吃",
        "occurred_at": "2026-11-20 12:30:00",
        "confidence": 0.85,
        "missing_fields": [],
        "raw_text": "识别到的原始文字，给用户看个依据",
    }

    raise ValueError：图片格式不支持 / 超过 5MB / 完全没认出来

    必须处理的四种情况（答辩会问）：
    1. 金额是 0 或没认出来 -> amount=None，missing_fields 加 "amount"
    2. 没有日期 -> 用今天，confidence 打 0.5 折
    3. 是多笔明细（一张小票买了 5 样东西）-> 先只取总额，别拆
    4. 图片不是小票（比如一张自拍）-> raise ValueError("没看出这是账单")

    TODO(C) 第 5-6 天
    """
    raise NotImplementedError("TODO(C) 第 5-6 天")


def needs_manual_review(result: dict) -> bool:
    """要不要强制走人工确认。

    规则：confidence 低于 LOW_CONFIDENCE，或 missing_fields 非空 -> True
    D 的页面据此决定"能不能直接入库"还是"必须先让用户改一遍"。

    TODO(C) 第 9-10 天
    """
    raise NotImplementedError("TODO(C) 第 9-10 天")
