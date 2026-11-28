"""add_transaction / list_transactions / get / update / delete 单元测试（Owner: A）

对应 tests/README.md 的分工表：add_transaction 校验、查询时间区间、改删。
跑法：pytest tests/test_ledger.py -v
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.ledger import (
    add_transaction,
    delete_transaction,
    get_transaction,
    list_transactions,
    update_transaction,
)


def _add(occurred_at="2026-11-05 12:00:00", amount=25.0, direction="expense", **extra) -> int:
    """快速记一笔，返回 id。测试大多只关心时间/金额/方向。"""
    return add_transaction(
        {"occurred_at": occurred_at, "amount": amount, "direction": direction, **extra}
    )


# ---------- add_transaction：四种必须报错的情况 ----------

def test_add_amount_非法一律报错(db):
    for bad in (None, "abc", 0, -5, 0.001):  # 0.001 -> 0 分，等于没花钱，也报错
        with pytest.raises(ValueError):
            _add(amount=bad)


def test_add_direction非法报错(db):
    with pytest.raises(ValueError):
        _add(direction="支出")  # 只认 expense / income，中文不行


def test_add_occurred_at_解析不出来就报错(db):
    for bad in (None, "", "昨天", "2026-13-01 00:00:00"):  # 13 月不存在
        with pytest.raises(ValueError):
            _add(occurred_at=bad)


def test_add_source_传错要报错_不悄悄改成manual(db):
    # 口径：默认值兜「没传」，报错兜「传错」。悄悄兜底的话，
    # 答辩统计「三种录入方式各占多少」就分不出来了。
    with pytest.raises(ValueError):
        _add(source="abc")


# ---------- add_transaction：默认值与归一化 ----------

def test_add_默认值_category其他_source_manual(db):
    tx_id = _add()

    row = get_transaction(tx_id)

    assert row["category"] == "其他"
    assert row["source"] == "manual"
    assert row["merchant"] is None and row["note"] is None and row["subcategory"] is None


def test_add_空白字符串一律存NULL(db):
    # 页面传 ""、模型传 None，最后库里都得是 NULL——统一口径
    tx_id = _add(merchant="   ", note="", raw_input=None, category=" ")

    row = get_transaction(tx_id)

    assert row["merchant"] is None and row["note"] is None
    assert row["category"] == "其他"  # 空白 category 也算没传


def test_add_confidence_非数字存NULL_越界夹到0到1(db):
    r1 = get_transaction(_add(confidence="高"))
    r2 = get_transaction(_add(confidence=1.5))
    r3 = get_transaction(_add(confidence=-0.2))
    r4 = get_transaction(_add(confidence=0.92))

    assert r1["confidence"] is None
    assert r2["confidence"] == 1.0
    assert r3["confidence"] == 0.0
    assert r4["confidence"] == 0.92


def test_add_occurred_at_五种输入格式_归一化结果(db):
    # 页面只给日期、模型带 T 或斜杠、少秒——入库后必须全是补零全格式。
    # 注意归一化只认两种"缺角"：10 位纯日期（补零点）、16 位少秒（补 :00）。
    variants = (
        (date(2026, 11, 20), "2026-11-20 00:00:00"),       # date 对象
        ("2026-11-20", "2026-11-20 00:00:00"),             # 纯日期
        ("2026-11-20 12:30", "2026-11-20 12:30:00"),       # 少秒
        ("2026/11/20 12:30", "2026-11-20 12:30:00"),       # 斜杠
        ("2026-11-20T12:30", "2026-11-20 12:30:00"),       # ISO 的 T
    )
    for i, (occurred, expected) in enumerate(variants):
        row = get_transaction(_add(occurred_at=occurred, amount=1 + i))
        assert row["occurred_at"] == expected, f"输入 {occurred!r} 没归一化"


def test_add_金额元转分_且新id是整数递增(db):
    id1 = _add(amount=25.5)
    id2 = _add(amount=0.05)

    assert isinstance(id1, int) and id2 == id1 + 1
    assert get_transaction(id1)["amount_cents"] == 2550
    assert get_transaction(id2)["amount_cents"] == 5


# ---------- list_transactions：区间与筛选 ----------

def test_list_闭区间_两端当天的账都要(db):
    _add("2026-11-01 00:00:00")
    _add("2026-11-15 12:00:00")
    _add("2026-11-30 23:59:59")

    rows = list_transactions("2026-11-01", "2026-11-30")

    assert len(rows) == 3


def test_list_未补零日期和补零写法结果一致(db):
    # 回归测试：'2026-11-3' 拼进 SQL 字符串比较会错位（悄悄漏账）
    _add("2026-11-05 12:00:00")

    assert list_transactions("2026-11-3", "2026-11-30") == list_transactions("2026-11-03", "2026-11-30")


def test_list_反区间报错(db):
    with pytest.raises(ValueError):
        list_transactions("2026-11-30", "2026-11-01")


def test_list_筛选_类别生效_空白不筛_方向大小写空格宽容(db):
    _add("2026-11-05 12:00:00", 10.0, category="餐饮")
    _add("2026-11-06 12:00:00", 20.0, direction="income")

    assert [r["category"] for r in list_transactions(category="餐饮")] == ["餐饮"]
    assert len(list_transactions(category="   ")) == 2          # 空白 = 不筛
    assert [r["direction"] for r in list_transactions(direction=" Income ")] == ["income"]
    with pytest.raises(ValueError):
        list_transactions(direction="支出")                       # 宽容不等于没底线


def test_list_排序最新在前_limit夹值(db):
    id1 = _add("2026-11-05 12:00:00")
    id2 = _add("2026-11-06 12:00:00")
    id3 = _add("2026-11-07 12:00:00")

    rows = list_transactions(limit=2)
    assert [r["id"] for r in rows] == [id3, id2]               # 倒序 + 截断

    assert len(list_transactions(limit=0)) == 1                # 0/负数夹成 1，不是「不限」
    assert len(list_transactions(limit=99999)) == 3            # 超上限夹到 1000，全表也不会拉爆


def test_list_返回行带元和分两份金额(db):
    _add(amount=25.5)

    row = list_transactions()[0]

    assert row["amount"] == 25.5 and row["amount_cents"] == 2550


# ---------- get / update / delete ----------

def test_get_不存在返回None(db):
    assert get_transaction(999) is None


def test_update_白名单外的字段直接报错(db):
    tx_id = _add()

    with pytest.raises(ValueError):
        update_transaction(tx_id, amout=99.0)   # 拼错的不悄悄忽略
    with pytest.raises(ValueError):
        update_transaction(tx_id, id=1, created_at="2026-01-01 00:00:00")  # 主键和入库时间不许改


def test_update_金额元转分_时间也归一化(db):
    tx_id = _add(amount=25.0)

    assert update_transaction(tx_id, amount=30.0, occurred_at="2026-11-06 12:30") is True

    row = get_transaction(tx_id)
    assert row["amount_cents"] == 3000
    assert row["occurred_at"] == "2026-11-06 12:30:00"


def test_update_没传字段或记录不存在_返回False(db):
    tx_id = _add()

    assert update_transaction(tx_id) is False            # 一个字段没动
    assert update_transaction(999, note="x") is False    # 记录不存在


def test_delete_存在True_不存在False(db):
    tx_id = _add()

    assert delete_transaction(tx_id) is True
    assert get_transaction(tx_id) is None
    assert delete_transaction(tx_id) is False
