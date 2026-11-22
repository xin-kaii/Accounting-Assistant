"""账单列表页的纯函数测试（Owner: C）

只测不碰界面的逻辑：时间范围换算、按天分组、小计、Markdown 表格。
真正的查询依赖 A 的 list_transactions，等它合并后由页面级验收覆盖。
"""

from __future__ import annotations

from datetime import date

from app.ui.page_bills import (
    _group_by_day,
    _range_for,
    _rows_table,
    _total,
)


def test_range_this_month():
    assert _range_for("本月", date(2026, 11, 23)) == ("2026-11-01", "2026-11-30")


def test_range_last_month():
    # 跨年也要对：1 月的上月是去年 12 月
    assert _range_for("上月", date(2026, 11, 23)) == ("2026-10-01", "2026-10-31")
    assert _range_for("上月", date(2026, 1, 15)) == ("2025-12-01", "2025-12-31")


def test_range_last_3_months():
    assert _range_for("近3个月", date(2026, 11, 23)) == ("2026-09-01", "2026-11-23")


def test_range_custom_swapped_dates_are_fixed():
    # 用户把开始/结束点反了，不能让查询返回空
    start, end = _range_for("自定义", date(2026, 11, 23),
                            custom_start=date(2026, 11, 20), custom_end=date(2026, 11, 10))
    assert start == "2026-11-10" and end == "2026-11-20"


def _rows():
    return [
        {"occurred_at": "2026-11-22 19:30:00", "amount": 36.0, "direction": "expense",
         "category": "餐饮", "merchant": "星巴克", "note": None, "source": "receipt"},
        {"occurred_at": "2026-11-22 12:00:00", "amount": 25.0, "direction": "expense",
         "category": "餐饮", "merchant": "沙县小吃", "note": "和同事AA", "source": "text"},
        {"occurred_at": "2026-11-21 09:00:00", "amount": 8000.0, "direction": "income",
         "category": "其他", "merchant": "公司", "note": None, "source": "manual"},
    ]


def test_group_by_day_keeps_desc_order():
    groups = _group_by_day(_rows())
    assert list(groups) == ["2026-11-22", "2026-11-21"]
    assert len(groups["2026-11-22"]) == 2


def test_total_only_counts_given_direction():
    rows = _rows()
    assert _total(rows, "expense") == 61.0
    assert _total(rows, "income") == 8000.0


def test_rows_table_marks_income_with_plus():
    table = _rows_table(_rows())
    assert "+¥8000.00" in table          # 收入带 +
    assert "-¥25.00" in table            # 支出带 -
    assert "小票" in table               # source 翻译成中文
    assert "沙县小吃" in table


def test_rows_table_escapes_pipe():
    rows = [{"occurred_at": "2026-11-22 12:00:00", "amount": 1.0, "direction": "expense",
             "category": "其他", "merchant": None, "note": "a|b", "source": "manual"}]
    assert "a｜b" in _rows_table(rows)    # 竖线不能把表格撑坏
