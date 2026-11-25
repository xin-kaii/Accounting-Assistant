"""小票识别模块的离线测试（Owner: C）

原则：**不测网络、不花钱**。真模型调用放在第 13 天的"陌生人复现"里手动跑一次即可。
这里只锁住那些"改一行代码就可能悄悄坏掉"的逻辑。
"""

from __future__ import annotations

import pytest

from app.ocr.receipt import (
    LOW_CONFIDENCE,
    ReceiptError,
    _extract_json,
    _normalize,
    _sniff_image_type,
    _to_datetime,
    extract_receipt,
    needs_manual_review,
)


# ---------- 入口校验：错的东西进来要报人话，不是抛 traceback ----------

def test_empty_image_rejected():
    with pytest.raises(ReceiptError):
        extract_receipt(b"")


def test_unsupported_mime_rejected():
    with pytest.raises(ReceiptError):
        extract_receipt(b"not-an-image", mime_type="image/gif")


def test_oversize_image_rejected():
    with pytest.raises(ReceiptError):
        extract_receipt(b"x" * (5 * 1024 * 1024 + 1))


def test_non_image_bytes_rejected_with_clear_message():
    """.gif / .pdf 改名成 .jpg 是最常见的"假图"，不能直接甩给模型。"""
    with pytest.raises(ReceiptError, match="不是图片"):
        extract_receipt(b"PK\x03\x04 this is a zip, renamed to .jpg")


def test_truncated_png_rejected():
    """文件头对、但内容截断的图，要报"打不开"，而不是把模型报错原样抛给用户。"""
    with pytest.raises(ReceiptError, match="打不开"):
        extract_receipt(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200)


@pytest.mark.parametrize(
    "head,expected",
    [
        (b"\xff\xd8\xff\xe0", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp"),
        (b"%PDF-1.4", None),
    ],
)
def test_sniff_image_type(head, expected):
    assert _sniff_image_type(head + b"rest") == expected


# ---------- 模型返回的脏数据 ----------

@pytest.mark.parametrize(
    "text,expected",
    [
        ('{"amount": 25}', {"amount": 25}),
        ('```json\n{"amount": 25}\n```', {"amount": 25}),
        ('好的，结果如下：{"amount": 25} 希望有帮助', {"amount": 25}),
    ],
)
def test_extract_json_tolerates_noise(text, expected):
    assert _extract_json(text) == expected


def test_extract_json_rejects_garbage():
    with pytest.raises(ReceiptError):
        _extract_json("对不起，我看不出这张图")


# ---------- 字段消毒 ----------

def test_amount_string_with_unit():
    assert _normalize({"amount": "25.00元"})["amount"] == 25.0


def test_invalid_category_falls_back():
    assert _normalize({"amount": 25, "category": "food"})["category"] == "其他"


def test_missing_amount_is_reported():
    result = _normalize({"amount": None, "confidence": 0.9})
    assert result["amount"] is None
    assert "amount" in result["missing_fields"]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-11-20 12:30:00", "2026-11-20 12:30:00"),
        ("2026/11/20 12:30", "2026-11-20 12:30:00"),
        ("2026-11-20", "2026-11-20 00:00:00"),
        ("2026年11月20日", "2026-11-20 00:00:00"),
    ],
)
def test_datetime_formats(raw, expected):
    assert _to_datetime(raw) == expected


def test_no_datetime_halves_confidence():
    """没认到时间：用今天顶，但置信度打对折（答辩会问）。"""
    result = _normalize({"amount": 25, "confidence": 0.9, "occurred_at": None})
    assert result["confidence"] == 0.45


# ---------- 人工复核判定 ----------

def test_low_confidence_needs_review():
    assert needs_manual_review({"confidence": LOW_CONFIDENCE - 0.1, "missing_fields": []})


def test_missing_field_needs_review():
    assert needs_manual_review({"confidence": 0.95, "missing_fields": ["amount"]})


def test_good_result_passes():
    assert not needs_manual_review({"confidence": 0.95, "missing_fields": []})


def test_dirty_input_needs_review():
    assert needs_manual_review(None)
