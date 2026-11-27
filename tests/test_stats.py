"""get_stats 单元测试（Owner: A）

对应 tests/README.md 的分工表：分类聚合、月度趋势、空数据不崩。
跑法：pytest tests/test_stats.py -v
"""

from __future__ import annotations

import pytest

from app.services.ledger import add_transaction
from app.services.stats import get_stats


def _expense(occurred_at: str, amount: float, category: str, **extra) -> None:
    """快速造一笔支出。测试只关心 occurred_at / amount / category。"""
    add_transaction(
        {"occurred_at": occurred_at, "amount": amount, "direction": "expense", "category": category, **extra}
    )


# ---------- 分类聚合 ----------

def test_分类聚合_按金额倒序_占比和笔数都对(db):
    _expense("2026-11-05 12:00:00", 300.0, "餐饮")
    _expense("2026-11-06 12:00:00", 300.0, "餐饮")
    _expense("2026-11-07 12:00:00", 400.0, "交通")

    stats = get_stats("2026-11-01", "2026-11-30")

    assert stats["total"] == 1000.0
    assert stats["count"] == 3
    assert stats["avg"] == 333.33  # 100000 分 / 3 ≈ 33333 分，先整分再转元
    # GROUP BY 后在 SQL 里按金额倒序，页面画饼图直接用
    assert stats["by_category"] == [
        {"category": "餐饮", "amount": 600.0, "ratio": 0.6, "count": 2},
        {"category": "交通", "amount": 400.0, "ratio": 0.4, "count": 1},
    ]


def test_收入不计入消费(db):
    _expense("2026-11-05 12:00:00", 100.0, "餐饮")
    add_transaction({"occurred_at": "2026-11-01 09:00:00", "amount": 5000.0, "direction": "income"})

    stats = get_stats("2026-11-01", "2026-11-30")

    assert stats["total"] == 100.0 and stats["count"] == 1


def test_类别筛选_只统计该类别(db):
    _expense("2026-11-05 12:00:00", 300.0, "餐饮")
    _expense("2026-11-06 12:00:00", 400.0, "交通")

    stats = get_stats("2026-11-01", "2026-11-30", category="餐饮")

    assert stats["total"] == 300.0 and stats["count"] == 1


# ---------- 单笔最高 ----------

def test_单笔最高_带商户和时间_商户可空(db):
    _expense("2026-11-05 12:00:00", 25.0, "餐饮", merchant="沙县小吃")
    _expense("2026-11-06 12:00:00", 300.0, "购物")  # 没填商户

    max_single = get_stats("2026-11-01", "2026-11-30")["max_single"]

    assert max_single["amount"] == 300.0
    assert max_single["merchant"] is None
    assert max_single["occurred_at"] == "2026-11-06 12:00:00"


# ---------- 月度趋势 ----------

def test_月度趋势_跨三个月_按月份排序(db):
    _expense("2026-11-10 12:00:00", 500.0, "餐饮")
    _expense("2026-10-10 12:00:00", 100.0, "交通")
    _expense("2026-09-10 12:00:00", 300.0, "购物")

    trend = get_stats("2026-09-01", "2026-11-30")["monthly_trend"]

    assert trend == [
        {"month": "2026-09", "amount": 300.0},
        {"month": "2026-10", "amount": 100.0},
        {"month": "2026-11", "amount": 500.0},
    ]


# ---------- 边界与校验（含本轮修的 bug 回归） ----------

def test_空数据不崩_返回零值和空列表(db):
    # 没有任何账单 -> 返回结构完整的"零值"，绝不抛异常（统计页会崩）
    stats = get_stats("2025-01-01", "2025-01-31")

    assert stats == {
        "total": 0.0,
        "count": 0,
        "avg": 0.0,
        "max_single": None,
        "by_category": [],
        "monthly_trend": [],
    }


def test_区间闭区间_两端当天的账都算(db):
    _expense("2026-11-01 00:00:00", 10.0, "餐饮")
    _expense("2026-11-15 12:00:00", 20.0, "餐饮")
    _expense("2026-11-30 23:59:59", 30.0, "餐饮")

    stats = get_stats("2026-11-01", "2026-11-30")

    assert stats["total"] == 60.0 and stats["count"] == 3


def test_未补零日期与补零写法结果完全一致(db):
    # 回归测试：strptime 放行 "2026-11-3"，过去会拼出和库里补零格式错位的
    # 区间下界，11/3 之后的账全部漏掉。修复后两种写法必须等价。
    _expense("2026-11-05 12:00:00", 100.0, "餐饮")

    assert get_stats("2026-11-3", "2026-11-30") == get_stats("2026-11-03", "2026-11-30")
    assert get_stats("2026-11-3", "2026-11-30")["total"] == 100.0


def test_区间倒置_抛ValueError(db):
    # 倒置区间是调用方的 bug，必须大声报错，不能静默返回"0 元"
    with pytest.raises(ValueError):
        get_stats("2026-11-30", "2026-11-01")


def test_非法日期_抛ValueError(db):
    for bad in ("2026-11", "2026年11月", "昨天", ""):
        with pytest.raises(ValueError):
            get_stats(bad, "2026-11-30")
