"""账单存取（Owner: A｜第 3-4 天完成）

这是全项目的地基：B 解析出来的、C 识别出来的、页面手动填的，最后都调这里的函数入库。
签名定了就不许改，改了另外三个人全崩。
"""

from __future__ import annotations

from datetime import datetime

from app.constants import (
    DEFAULT_CATEGORY,
    DIRECTIONS,
    SOURCE_MANUAL,
    SOURCES,
)
from app.db.conn import DATETIME_FMT, now_str, tx
from app.money import to_cents, to_yuan


def add_transaction(record: dict) -> int:
    """存一笔账，返回新的 id。

    record 必填：
        occurred_at : 'YYYY-MM-DD HH:MM:SS'  钱是什么时候花的
        amount      : float > 0               金额，**单位：元**（如 25.5）
                                              入库时用 money.to_cents() 转成分存储
        direction   : 'expense' | 'income'

    record 选填（缺了用默认值）：
        category    : 默认 "其他"
        subcategory / merchant / note : 默认 None
        source      : 默认 "manual"（C 的页面应该显式传 text/receipt/manual）
        raw_input   : 默认 None（C 的页面传用户原话或 OCR 原文）
        confidence  : 默认 None

    raise ValueError：下面四种情况都要抛，不要静默兜底
        1. amount <= 0
        2. direction 不是 expense / income
        3. occurred_at 格式不对
        4. source 传了非法值（比如 "abc"）—— 这一条最容易漏：
           如果把它悄悄改成 "manual"，C 写错了也没人知道，
           答辩统计「三种录入方式各占多少」时就分不出来了。
           口径：默认值兜「没传」，报错兜「传错」。

    TODO(A) 第 3-4 天
    """
    # ---------- 1. 必填三项：时间 / 金额 / 方向 ----------
    occurred_at = (record.get("occurred_at") or "").strip()
    try:
        datetime.strptime(occurred_at, DATETIME_FMT)
    except ValueError:
        raise ValueError(
            f"occurred_at 必须是 'YYYY-MM-DD HH:MM:SS'，收到 {occurred_at!r}"
        ) from None

    amount = record.get("amount")
    if amount is None:
        raise ValueError("amount 不能为空")
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValueError(f"amount 必须是数字，收到 {record.get('amount')!r}") from None
    if amount <= 0:
        raise ValueError(f"amount 必须大于 0，收到 {amount}")

    direction = record.get("direction")
    if direction not in DIRECTIONS:
        raise ValueError(f"direction 只能是 {DIRECTIONS}，收到 {direction!r}")

    # ---------- 2. 来源：没传就兜默认，传错就报错 ----------
    source = record.get("source") or SOURCE_MANUAL
    if source not in SOURCES:
        raise ValueError(f"source 只能是 {SOURCES}，收到 {source!r}")

    # ---------- 3. 入库（金额转成分） ----------
    with tx() as conn:
        cur = conn.execute(
            """
            INSERT INTO transactions
                (occurred_at, amount, direction, category, subcategory,
                 merchant, note, source, raw_input, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                occurred_at,
                to_cents(amount),
                direction,
                record.get("category") or DEFAULT_CATEGORY,
                record.get("subcategory"),
                record.get("merchant"),
                record.get("note"),
                source,
                record.get("raw_input"),
                record.get("confidence"),
                now_str(),
            ),
        )
        return int(cur.lastrowid)


def list_transactions(
    start: str | None = None,
    end: str | None = None,
    category: str | None = None,
    direction: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """按条件查账单，按 occurred_at 倒序（最新的在前）。

    start / end 都是 'YYYY-MM-DD'，闭区间（含当天）。
    账单列表页、对话页都调它。

    TODO(A) 第 3-4 天
    """
    sql = "SELECT * FROM transactions WHERE 1 = 1"
    params: list[object] = []

    # 闭区间：start 从当天 00:00:00 起，end 到当天 23:59:59 止
    if start:
        sql += " AND occurred_at >= ?"
        params.append(f"{start} 00:00:00")
    if end:
        sql += " AND occurred_at <= ?"
        params.append(f"{end} 23:59:59")
    if category:
        sql += " AND category = ?"
        params.append(category)
    if direction:
        sql += " AND direction = ?"
        params.append(direction)

    sql += " ORDER BY occurred_at DESC, id DESC LIMIT ?"
    params.append(int(limit))

    with tx() as conn:
        rows = conn.execute(sql, params).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["amount"] = to_yuan(item["amount"])   # 分 -> 元，界面直接用
        result.append(item)
    return result


def get_transaction(tx_id: int) -> dict | None:
    """查单条，不存在返回 None。TODO(A) 第 5 天"""
    raise NotImplementedError("TODO(A) 第 5 天")


def update_transaction(tx_id: int, **fields) -> bool:
    """改一条（用户在确认页改了金额/类别后调用）。返回是否改成功。

    改过之后，B 会把 (raw_input, 错的, 对的) 写进 corrections 表。
    TODO(A) 第 5 天
    """
    raise NotImplementedError("TODO(A) 第 5 天")


def delete_transaction(tx_id: int) -> bool:
    """删一条。TODO(A) 第 5 天"""
    raise NotImplementedError("TODO(A) 第 5 天")


def record_correction(raw_input: str, wrong: dict, correct: dict) -> None:
    """记一次用户修正，给 B 的 prompt 当 few-shot 例子用（加分项，第 10 天后有空再做）。"""
    raise NotImplementedError("TODO(A) 加分项，可跳过")
