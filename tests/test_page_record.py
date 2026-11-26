"""记账页的纯函数测试（Owner: C）

重点守住两件容易悄悄坏掉的事：
1. 卡片组装记录时，source 必须继承（小票识别传 receipt，不能被写死成 text）
2. 低置信度 / 缺字段时必须进人工核对流程
"""

from __future__ import annotations

from app.ui.page_record import _compose_record, _needs_review

CARD_VALUES = dict(
    amount=13.4,
    direction="expense",
    category="餐饮",
    occurred_at="2026-11-26 17:06:00",
    merchant="炒饭专家",
    note=None,
    subcategory=None,
)


def test_compose_keeps_receipt_source():
    """小票识别入库后，数据库里必须是 source=receipt（答辩要统计录入方式）。"""
    record = _compose_record(
        {"source": "receipt", "confidence": 0.9, "raw_input": "图上原文"},
        **CARD_VALUES,
    )
    assert record["source"] == "receipt"
    assert record["raw_input"] == "图上原文"
    assert record["confidence"] == 0.9


def test_compose_defaults_source_to_text():
    assert _compose_record({}, **CARD_VALUES)["source"] == "text"


def test_compose_strips_blank_text_fields():
    record = _compose_record(
        {}, **{**CARD_VALUES, "merchant": "  ", "note": "  ", "subcategory": ""}
    )
    assert record["merchant"] is None
    assert record["note"] is None
    assert record["subcategory"] is None


def test_compose_rounds_amount():
    assert _compose_record({}, **{**CARD_VALUES, "amount": 13.4})["amount"] == 13.4


def test_needs_review_when_low_confidence():
    assert _needs_review({"confidence": 0.3, "missing_fields": []})


def test_needs_review_when_missing_fields():
    assert _needs_review({"confidence": 0.95, "missing_fields": ["amount"]})


def test_no_extra_review_for_confident_complete_record():
    assert not _needs_review({"confidence": 0.95, "missing_fields": []})
