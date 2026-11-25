"""账单列表页（Owner: C｜第 5-6 天）

直接调 A 的 list_transactions()，没有跨人依赖。

四件事：
    1. 筛选：时间范围（本月 / 上月 / 近 3 个月 / 自定义）、类别、收支
    2. 按天分组，每天显示小计
    3. 顶部汇总：笔数 / 支出合计 / 收入合计
    4. 空数据时给一句"去记账页试试"，不要白屏

⚠️ 表格用 Markdown 手写，不用 st.dataframe：
   st.dataframe 要 import pandas，而这台机器上 numpy.random 的 DLL 被应用控制策略拦了，
   pandas 一 import 就崩（详见 docs/03 问题 9）。等环境修好再换回 st.dataframe。
"""

from __future__ import annotations

import calendar
from datetime import date

import streamlit as st

from app.constants import CATEGORIES, DIRECTION_EXPENSE, DIRECTION_INCOME

try:  # A 的查询
    from app.services.ledger import list_transactions as _list_transactions_from_a
except Exception:  # pragma: no cover
    _list_transactions_from_a = None

_DIRECTION_LABELS = {DIRECTION_EXPENSE: "支出", DIRECTION_INCOME: "收入"}
_SOURCE_LABELS = {"text": "文字", "receipt": "小票", "manual": "手动"}
_ALL = "全部"


def _shift_month(day: date, months: int) -> date:
    year, month = day.year, day.month + months
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)


def _month_bounds(day: date) -> tuple[str, str]:
    """这个月 1 号到月底，返回 'YYYY-MM-DD'。"""
    start = day.replace(day=1)
    end = day.replace(day=calendar.monthrange(day.year, day.month)[1])
    return start.isoformat(), end.isoformat()


def _range_for(picked: str, today: date,
               custom_start: date | None = None, custom_end: date | None = None) -> tuple[str, str]:
    """把下拉选的时间范围转成 A 要的 start/end（闭区间）。"""
    if picked == "本月":
        return _month_bounds(today)
    if picked == "上月":
        # 注意：_shift_month 返回的是那个月的 1 号，直接取它的月底才是"上月"
        return _month_bounds(_shift_month(today, -1))
    if picked == "近3个月":
        return _shift_month(today, -2).isoformat(), today.isoformat()
    start = custom_start or _shift_month(today, -1)
    end = custom_end or today
    if start > end:   # 用户把日期点反了，别让查询返回空
        start, end = end, start
    return start.isoformat(), end.isoformat()


def _fetch(start: str, end: str, category: str | None, direction: str | None) -> list[dict]:
    """调 A 的查询。返回 [] 表示没数据，抛异常由调用方处理。"""
    if _list_transactions_from_a is None:
        raise NotImplementedError
    return _list_transactions_from_a(
        start=start, end=end, category=category, direction=direction, limit=500
    )


def _group_by_day(rows: list[dict]) -> dict[str, list[dict]]:
    """按 occurred_at 的日期分组，保持"最新的在前"的顺序。"""
    groups: dict[str, list[dict]] = {}
    for row in rows:
        day = str(row.get("occurred_at") or "")[:10]
        groups.setdefault(day, []).append(row)
    return groups


def _total(rows: list[dict], direction: str) -> float:
    return sum(float(r.get("amount") or 0) for r in rows if r.get("direction") == direction)


def _rows_table(rows: list[dict]) -> str:
    """手写 Markdown 表格（不用 pandas）。"""
    lines = ["| 时间 | 金额 | 类别 | 商户 | 备注 | 来源 |", "| --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        amount = float(row.get("amount") or 0)
        sign = "+" if row.get("direction") == DIRECTION_INCOME else "-"
        lines.append(
            "| {time} | {sign}¥{amount:.2f} | {category} | {merchant} | {note} | {source} |".format(
                time=str(row.get("occurred_at") or "")[11:16],
                sign=sign,
                amount=amount,
                category=row.get("category") or "-",
                merchant=row.get("merchant") or "-",
                note=(row.get("note") or "-").replace("|", "｜"),
                source=_SOURCE_LABELS.get(row.get("source") or "", row.get("source") or "-"),
            )
        )
    return "\n".join(lines)


def render() -> None:
    """渲染账单列表。"""
    st.subheader("账单列表")
    today = date.today()

    col_range, col_category, col_direction = st.columns([2, 2, 2])
    with col_range:
        picked = st.radio("时间范围", ["本月", "上月", "近3个月", "自定义"],
                          horizontal=True, key="bills_range")
    with col_category:
        category = st.selectbox("类别", [_ALL, *CATEGORIES], key="bills_category")
    with col_direction:
        direction_label = st.radio("收支", [_ALL, "支出", "收入"],
                                   horizontal=True, key="bills_direction")

    custom_start = custom_end = None
    if picked == "自定义":
        c1, c2 = st.columns(2)
        custom_start = c1.date_input("开始日期", value=_shift_month(today, -1), key="bills_start")
        custom_end = c2.date_input("结束日期", value=today, key="bills_end")

    start, end = _range_for(picked, today, custom_start, custom_end)
    category_value = None if category == _ALL else category
    direction_value = {"支出": DIRECTION_EXPENSE, "收入": DIRECTION_INCOME}.get(direction_label)

    try:
        rows = _fetch(start, end, category_value, direction_value)
    except NotImplementedError:
        st.warning("A 的 `list_transactions()` 还没接通，账单页暂时查不到数据。"
                   "等他那边合并之后，这里会自动有数据，不用改页面。")
        st.caption(f"当前查询区间：{start} ~ {end}")
        return
    except Exception as exc:  # noqa: BLE001 - 数据库坏了也不能让页面崩
        st.error(f"查询失败（{type(exc).__name__}: {exc}）")
        return

    st.caption(f"查询区间：{start} ~ {end} ｜ 共 {len(rows)} 笔")

    if not rows:
        st.info("这个条件下还没有账单。去 **✍️ 记账** 页记一笔试试。")
        return

    expense, income = _total(rows, DIRECTION_EXPENSE), _total(rows, DIRECTION_INCOME)
    m1, m2, m3 = st.columns(3)
    m1.metric("笔数", len(rows))
    m2.metric("支出合计", f"¥{expense:.2f}")
    m3.metric("收入合计", f"¥{income:.2f}")

    st.divider()
    for day, day_rows in _group_by_day(rows).items():
        day_expense, day_income = _total(day_rows, DIRECTION_EXPENSE), _total(day_rows, DIRECTION_INCOME)
        subtitle = f"支出 ¥{day_expense:.2f}"
        if day_income:
            subtitle += f" · 收入 ¥{day_income:.2f}"
        st.markdown(f"**{day}**　{subtitle}　（{len(day_rows)} 笔）")
        st.markdown(_rows_table(day_rows))
        st.write("")

    st.caption("改 / 删账单要等 A 的 update_transaction / delete_transaction 接通，第 5 天之后再加。")
