"""日期 / 月份的统一解析与归一化

为什么要有这一层：库里的 occurred_at 是**补零**的 'YYYY-MM-DD HH:MM:SS'，
查询靠字符串比较当时间比较。而 strptime 对 %m、%d 很宽容——"2026-1"、
"2026-11-3" 都能解析成功。如果把原文本直接拼进 SQL，"2026-11-3 00:00:00"
和 "2026-11-03 12:00:00" 比较就会错位：不报错，只是悄悄少查/多查。

所以规则是：**解析一次，回写成补零格式，再用**。
ledger / stats / budget 三处都调这里，别各写一套。
"""

from __future__ import annotations

from datetime import date, datetime

DAY_FMT = "%Y-%m-%d"
MONTH_FMT = "%Y-%m"


def parse_day(value: object, name: str = "date") -> str:
    """'YYYY-MM-DD' 解析并归一化：'2026-11-3' -> '2026-11-03'。

    date / datetime 对象也收。解析不出来（空值、"2026-11"、"昨天"）抛 ValueError。
    """
    if isinstance(value, date):      # datetime 是 date 的子类，一起覆盖
        return value.strftime(DAY_FMT)
    text = str(value or "").strip()
    try:
        parsed = datetime.strptime(text, DAY_FMT)
    except ValueError:
        raise ValueError(f"{name} 必须是 'YYYY-MM-DD'，收到 {value!r}") from None
    return parsed.strftime(DAY_FMT)


def parse_month(value: object, name: str = "month") -> str:
    """'YYYY-MM' 解析并归一化：'2026-1' -> '2026-01'。解析不出来抛 ValueError。"""
    text = str(value or "").strip()
    try:
        parsed = datetime.strptime(text, MONTH_FMT)
    except ValueError:
        raise ValueError(f"{name} 必须是 'YYYY-MM'，收到 {value!r}") from None
    return parsed.strftime(MONTH_FMT)
