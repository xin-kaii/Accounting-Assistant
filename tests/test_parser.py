"""B 的 parser / classifier 验收（第 5-6 天）。

原则：不花钱、不碰网络。
- 字段清洗（_normalize_record）是纯函数，直接测
- 真模型路径用 monkeypatch 换掉 client.chat_json
- 降级路径用 monkeypatch 让 client.chat_json 抛 LLMError

运行：
    pytest tests/test_parser.py -v
"""

from __future__ import annotations

from app import config
from app.llm import classifier, client, parser


# ---------- _normalize_record：把模型返回清洗成 9 个字段 ----------

def test_normalize_keeps_valid_record():
    raw = {
        "amount": 25.5,
        "direction": "income",
        "category": "餐饮",
        "subcategory": None,
        "merchant": None,
        "note": None,
        "occurred_at": "2026-11-20 12:00:00",
        "confidence": 0.9,
        "missing_fields": [],
    }
    out = parser._normalize_record(raw)
    assert out["amount"] == 25.5
    assert out["direction"] == "income"
    assert out["category"] == "餐饮"
    assert out["confidence"] == 0.9
    assert out["missing_fields"] == []


def test_normalize_string_amount_and_negative():
    # 模型可能返回字符串金额、或把退款写成负数，这里统一成正值数字
    out = parser._normalize_record({"amount": "-30.5", "direction": "expense"})
    assert out["amount"] == 30.5


def test_normalize_bad_direction_and_category():
    # 非法方向按支出、非法类别按“其他”
    out = parser._normalize_record({"amount": 30, "direction": "退款", "category": "乱写"})
    assert out["direction"] == "expense"
    assert out["category"] == "其他"


def test_normalize_missing_amount_adds_missing_field():
    out = parser._normalize_record({"amount": "abc"})
    assert out["amount"] is None
    assert "amount" in out["missing_fields"]


def test_normalize_clamps_confidence():
    out = parser._normalize_record({"amount": 10, "confidence": 5})
    assert out["confidence"] == 1.0
    out2 = parser._normalize_record({"amount": 10, "confidence": "abc"})
    assert out2["confidence"] == 0.5


# ---------- parse_record：真模型路径 + 降级 ----------

def test_parse_record_real_path_normalizes(monkeypatch):
    monkeypatch.setattr(config, "llm_ready", lambda: True)
    monkeypatch.setattr(
        client,
        "chat_json",
        lambda system, user: {
            "amount": "25",
            "direction": "expense",
            "category": "餐饮",
            "confidence": "0.9",
            "missing_fields": [],
        },
    )
    out = parser.parse_record("午饭25")
    assert out["amount"] == 25.0
    assert out["category"] == "餐饮"
    assert out["direction"] == "expense"


def test_parse_record_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr(config, "llm_ready", lambda: True)

    def boom(system, user):
        raise client.LLMError("网络挂了")

    monkeypatch.setattr(client, "chat_json", boom)
    out = parser.parse_record("午饭25")
    # 真模型失败后降级到 mock，金额/类别仍对
    assert out["amount"] == 25.0
    assert out["category"] == "餐饮"


def test_parse_record_mock_path_when_not_ready(monkeypatch):
    monkeypatch.setattr(config, "llm_ready", lambda: False)
    out = parser.parse_record("工资5000")
    assert out["amount"] == 5000.0
    assert out["direction"] == "income"


# ---------- classifier：真模型路径 + 降级 ----------

def test_classify_mock_path(monkeypatch):
    monkeypatch.setattr(config, "llm_ready", lambda: False)
    assert classifier.classify("星巴克") == ("餐饮", 0.7)
    assert classifier.classify("打车") == ("交通", 0.7)
    assert classifier.classify("不知道") == ("其他", 0.3)


def test_classify_real_path(monkeypatch):
    monkeypatch.setattr(config, "llm_ready", lambda: True)
    monkeypatch.setattr(
        client,
        "chat_json",
        lambda system, user: {"category": "购物", "confidence": 0.95},
    )
    assert classifier.classify("优衣库") == ("购物", 0.95)


def test_classify_real_path_bad_category(monkeypatch):
    monkeypatch.setattr(config, "llm_ready", lambda: True)
    monkeypatch.setattr(
        client,
        "chat_json",
        lambda system, user: {"category": "乱写", "confidence": 0.9},
    )
    cat, _ = classifier.classify("x")
    assert cat == "其他"


def test_classify_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr(config, "llm_ready", lambda: True)

    def boom(system, user):
        raise client.LLMError("挂了")

    monkeypatch.setattr(client, "chat_json", boom)
    assert classifier.classify("打车") == ("交通", 0.7)