"""check_budget / set_budget 单元测试（Owner: A）

对应 tests/README.md 的分工表：超支边界 99%、刚好 100%、100.01%
（任务板上的原话：9999 分 -> warn；10000 分 -> warn；10001 分 -> over）。
跑法：pytest tests/test_budget.py -v
"""

from __future__ import annotations

import pytest

from app.services.budget import check_budget, delete_budget, get_budgets, set_budget
from app.services.ledger import add_transaction


def _expense(occurred_at: str, amount: float, category: str) -> None:
    add_transaction(
        {"occurred_at": occurred_at, "amount": amount, "direction": "expense", "category": category}
    )


def _set(category: str, amount: float, month: str = "2026-11") -> None:
    set_budget(month, amount, category)


# ---------- 超支边界（任务板点名的用例） ----------

def test_超支边界_9999分warn_10000分warn_10001分over(db):
    # 预算都是 100 元 = 10000 分，三类分别花 9999 / 10000 / 10001 分
    _set("交通", 100)
    _set("购物", 100)
    _set("娱乐", 100)
    _expense("2026-11-05 12:00:00", 99.99, "交通")
    _expense("2026-11-06 12:00:00", 100.00, "购物")
    _expense("2026-11-07 12:00:00",  50.00, "娱乐")
    _expense("2026-11-08 12:00:00",  50.01, "娱乐")

    rows = {r["category"]: r for r in check_budget("2026-11")}

    # 99.99% -> warn；刚好 100% -> warn（不算超支）；100.01% -> over
    assert rows["交通"]["level"] == "warn"
    assert rows["购物"]["level"] == "warn" and rows["购物"]["ratio"] == 1.0
    assert rows["娱乐"]["level"] == "over"
    # 边界三个值必须都由「分」算出来，浮点转元再算就会错
    assert rows["交通"]["spent"] == 99.99 and rows["购物"]["spent"] == 100.0


def test_档位说明_ratio小于70算ok(db):
    _set("餐饮", 100)
    _expense("2026-11-05 12:00:00", 69.99, "餐饮")

    rows = check_budget("2026-11")

    assert rows[0]["level"] == "ok"


# ---------- set_budget：UPSERT 与校验 ----------

def test_set_budget_重复设置_覆盖而不是新增(db):
    _set("餐饮", 800)
    _set("餐饮", 900)

    got = get_budgets("2026-11")

    assert len(got) == 1
    assert got[0] == {"category": "餐饮", "amount": 900.0}  # 单位是元


def test_set_budget_未补零月份_归一化成2026_01(db):
    # 回归测试：strptime 放行 "2026-1"，过去会原样入库，
    # 和账单侧的 "2026-01" 永远匹配不上，预算变成孤儿数据。
    _set("餐饮", 100, month="2026-1")
    _expense("2026-01-15 12:00:00", 40.0, "餐饮")

    assert [b for b in get_budgets("2026-01") if b["category"] == "餐饮"][0]["amount"] == 100.0
    row = [r for r in check_budget("2026-01") if r["category"] == "餐饮"][0]
    assert row["spent"] == 40.0 and row["ratio"] == 0.4 and row["level"] == "ok"


def test_set_budget_非法输入_抛ValueError(db):
    with pytest.raises(ValueError):
        set_budget("2026年11月", 100)          # 月份格式错
    with pytest.raises(ValueError):
        set_budget("2026-11", 100, "餐饮x")    # 不在 10 个固定分类里
    with pytest.raises(ValueError):
        set_budget("2026-11", -5)              # 负数
    with pytest.raises(ValueError):
        set_budget("2026-11", "很多")          # 非数字


# ---------- check_budget：口径与排序 ----------

def test_没设预算的月份_返回空列表(db):
    assert check_budget("2026-10") == []


def test_总预算_包含没设预算的类别(db):
    # 总预算 1300，花了 920(餐饮) + 100(人情，没给"人情"设预算) = 1020
    _set("", 1300)
    _set("餐饮", 800)
    _expense("2026-11-05 12:00:00", 920.0, "餐饮")
    _expense("2026-11-06 12:00:00", 100.0, "人情")

    rows = {r["category"]: r for r in check_budget("2026-11")}

    assert rows[""]["spent"] == 1020.0 and rows[""]["level"] == "warn"  # 1020/1300 ≈ 78%
    assert rows["餐饮"]["spent"] == 920.0 and rows["餐饮"]["level"] == "over"  # 920/800 = 115%


def test_排序_总预算第一_其余按比例从高到低(db):
    _set("", 1300)
    _set("餐饮", 800)
    _set("交通", 100)
    _expense("2026-11-05 12:00:00", 920.0, "餐饮")   # 115%
    _expense("2026-11-06 12:00:00", 50.0, "交通")    # 50%

    rows = check_budget("2026-11")

    assert [r["category"] for r in rows] == ["", "餐饮", "交通"]


def test_预算0元_有支出判over_没有支出算ok(db):
    _set("通讯", 0)
    _set("娱乐", 0)
    _expense("2026-11-05 12:00:00", 30.0, "通讯")

    rows = {r["category"]: r for r in check_budget("2026-11")}

    assert rows["通讯"]["level"] == "over" and rows["通讯"]["ratio"] == float("inf")
    assert rows["娱乐"]["level"] == "ok" and rows["娱乐"]["ratio"] == 0.0


# ---------- delete_budget ----------

def test_删除预算_存在返回True_不存在返回False(db):
    _set("餐饮", 100)

    assert delete_budget("2026-11", "餐饮") is True
    assert delete_budget("2026-11", "餐饮") is False  # 再删一次：不存在
    assert get_budgets("2026-11") == []
