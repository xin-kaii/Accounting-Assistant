"""B 的 query_parser 验收（第 7-8 天）。

原则：不花钱、不碰网络。
- autouse fixture 默认把所有测试强制走 mock 路径
- _normalize_query 是纯函数直接测
- 真模型路径 monkeypatch client.chat_json
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app import config
from app.llm import client, query_parser


@pytest.fixture(autouse=True)
def _force_mock_path(monkeypatch):
    """默认走离线路径，测试不花钱不碰网络。"""
    monkeypatch.setattr(config, "llm_ready", lambda: False)


def _today():
    return datetime.now().date()


def _last_month_range():
    first_this = _today().replace(day=1)
    last_prev = first_this - timedelta(days=1)
    return last_prev.replace(day=1), last_prev


# ---------- mock 路径：metric ----------

def test_sum_with_category_and_last_month():
    start, end = _last_month_range()
    q = query_parser.parse_query("上个月吃饭花了多少")
    assert q == {
        "metric": "sum",
        "time_start": start.strftime("%Y-%m-%d"),
        "time_end": end.strftime("%Y-%m-%d"),
        "category": "餐饮",
        "direction": "expense",
    }


def test_sum_default_time_is_this_month():
    today = _today()
    q = query_parser.parse_query("吃饭花了多少")
    assert q["metric"] == "sum"
    assert q["time_start"] == today.replace(day=1).strftime("%Y-%m-%d")
    assert q["time_end"] == today.strftime("%Y-%m-%d")
    assert q["category"] == "餐饮"


def test_rank_wins_over_sum_keyword():
    q = query_parser.parse_query("这个月哪类花得最多")
    assert q["metric"] == "rank"
    assert q["category"] is None


def test_count():
    q = query_parser.parse_query("这个月记了几笔")
    assert q["metric"] == "count"


def test_recent_n_days():
    today = _today()
    q = query_parser.parse_query("最近30天打车花了多少")
    assert q["metric"] == "sum"
    assert q["time_start"] == (today - timedelta(days=30)).strftime("%Y-%m-%d")
    assert q["time_end"] == today.strftime("%Y-%m-%d")
    assert q["category"] == "交通"


def test_this_year():
    today = _today()
    q = query_parser.parse_query("今年花了多少")
    assert q["time_start"] == today.replace(month=1, day=1).strftime("%Y-%m-%d")
    assert q["time_end"] == today.strftime("%Y-%m-%d")


def test_last_week():
    today = _today()
    this_monday = today - timedelta(days=today.weekday())
    q = query_parser.parse_query("上周吃饭花了多少")
    assert q["time_start"] == (this_monday - timedelta(days=7)).strftime("%Y-%m-%d")
    assert q["time_end"] == (this_monday - timedelta(days=1)).strftime("%Y-%m-%d")


def test_today_and_yesterday():
    today = _today()
    q1 = query_parser.parse_query("今天花了多少")
    assert q1["time_start"] == q1["time_end"] == today.strftime("%Y-%m-%d")
    q2 = query_parser.parse_query("昨天花了多少")
    y = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    assert q2["time_start"] == q2["time_end"] == y


def test_income_direction():
    q = query_parser.parse_query("这个月工资收入多少")
    assert q["direction"] == "income"
    assert q["metric"] == "sum"


def test_compare_covers_two_months():
    today = _today()
    start, _ = _last_month_range()
    q = query_parser.parse_query("这个月比上个月多花了吗")
    assert q["metric"] == "compare"
    assert q["time_start"] == start.strftime("%Y-%m-%d")
    assert q["time_end"] == today.strftime("%Y-%m-%d")


def test_unknown_question_raises():
    with pytest.raises(ValueError):
        query_parser.parse_query("你好呀")


def test_category_only_raises():
    with pytest.raises(ValueError):
        query_parser.parse_query("吃饭")


# ---------- _normalize_query：真模型输出清洗 ----------

def test_normalize_valid():
    out = query_parser._normalize_query({
        "metric": "sum",
        "time_start": "2026-10-01",
        "time_end": "2026-10-31",
        "category": "餐饮",
        "direction": "expense",
    })
    assert out == {
        "metric": "sum",
        "time_start": "2026-10-01",
        "time_end": "2026-10-31",
        "category": "餐饮",
        "direction": "expense",
    }


def test_normalize_bad_metric_raises():
    with pytest.raises(ValueError):
        query_parser._normalize_query({
            "metric": "avg", "time_start": "2026-10-01", "time_end": "2026-10-31",
        })


def test_normalize_bad_date_raises():
    with pytest.raises(ValueError):
        query_parser._normalize_query({
            "metric": "sum", "time_start": "2026/10/01", "time_end": "2026-10-31",
        })


def test_normalize_start_after_end_raises():
    with pytest.raises(ValueError):
        query_parser._normalize_query({
            "metric": "sum", "time_start": "2026-11-26", "time_end": "2026-11-01",
        })


def test_normalize_bad_category_to_none():
    out = query_parser._normalize_query({
        "metric": "sum", "time_start": "2026-10-01", "time_end": "2026-10-31",
        "category": "乱写", "direction": "expense",
    })
    assert out["category"] is None


def test_normalize_bad_direction_to_expense():
    out = query_parser._normalize_query({
        "metric": "sum", "time_start": "2026-10-01", "time_end": "2026-10-31",
        "category": None, "direction": "退款",
    })
    assert out["direction"] == "expense"


# ---------- 真模型路径（monkeypatch，不花钱） ----------

def test_real_path_normalizes(monkeypatch):
    monkeypatch.setattr(config, "llm_ready", lambda: True)
    monkeypatch.setattr(client, "chat_json", lambda system, user: {
        "metric": "rank", "time_start": "2026-11-01", "time_end": "2026-11-26",
        "category": None, "direction": "expense",
    })
    q = query_parser.parse_query("这个月哪类花得最多")
    assert q["metric"] == "rank"
    assert q["time_start"] == "2026-11-01"


def test_real_path_bad_output_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr(config, "llm_ready", lambda: True)
    monkeypatch.setattr(client, "chat_json", lambda system, user: {"metric": "avg"})
    start, end = _last_month_range()
    q = query_parser.parse_query("上个月吃饭花了多少")
    assert q == {
        "metric": "sum",
        "time_start": start.strftime("%Y-%m-%d"),
        "time_end": end.strftime("%Y-%m-%d"),
        "category": "餐饮",
        "direction": "expense",
    }


def test_real_path_llm_error_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr(config, "llm_ready", lambda: True)

    def boom(system, user):
        raise client.LLMError("网络挂了")

    monkeypatch.setattr(client, "chat_json", boom)
    q = query_parser.parse_query("吃饭花了多少")
    assert q["metric"] == "sum"
    assert q["category"] == "餐饮"