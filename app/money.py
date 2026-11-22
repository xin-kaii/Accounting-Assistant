"""金额换算（Owner: A）

⭐ **全项目的金额规则，只有这一条：**

    边界用「元」，存储用「分」

- 用户输入、模型输出、页面显示  -> 元（float，如 25.00）
- 数据库存储、统计累加、预算比较 -> 分（int，如 2500）

**为什么**：浮点累加会出现 `0.1 + 0.2 = 0.30000000000000004`，
统计 120 笔之后 `spent` 可能是 `799.9999999`，于是"刚好花完 800 元"被判成
"还没超支"——而题目里这个边界是要在答辩上讲清楚的。

**怎么用**：只允许在两个地方转换
- 入库前：`to_cents(元)`
- 出库后：`to_yuan(分)`

业务逻辑里**不要手写 `* 100` 或 `/ 100`**，一律调这里的函数。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def to_cents(yuan: float | int | str) -> int:
    """元 -> 分。四舍五入到整分。

    >>> to_cents(25)
    2500
    >>> to_cents(25.5)
    2550
    >>> to_cents("0.01")
    1

    注意：转成 Decimal 前先 str()，避免把 float 的误差带进去。
    25.1 * 100 在浮点里是 2509.9999999999995，而 Decimal("25.1") * 100 是 2510。
    """
    d = Decimal(str(yuan)) * Decimal(100)
    return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def to_yuan(cents: int) -> float:
    """分 -> 元。仅用于展示和统计结果的返回。

    >>> to_yuan(2500)
    25.0

    ⚠️ 一定要返回 float，不能返回 Decimal。
    因为 `Decimal("1480.8") == 1480.8` 是 **False**，页面拿去和数字字面量比较会踩坑。
    内部先走 Decimal 保证精确到分，最后一步才转 float。
    """
    return float(Decimal(int(cents)) / Decimal(100))


def fmt_yuan(cents: int) -> str:
    """分 -> 带符号的字符串，给页面直接显示用。

    >>> fmt_yuan(2500)
    '¥25.00'
    >>> fmt_yuan(5)
    '¥0.05'
    """
    return f"¥{to_yuan(cents):.2f}"


def parse_yuan_text(text: str) -> int | None:
    """从"25元""25块""25.5"这类文本里抠出分。抠不到返回 None。

    给 mock_llm 和规则兜底用——金额是纯数字，正则比模型可靠。
    """
    import re

    m = re.search(r"(\d+(?:\.\d{1,2})?)", text)
    return to_cents(m.group(1)) if m else None
