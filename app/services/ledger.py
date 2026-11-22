"""账单存取（Owner: A｜第 3-4 天完成）

这是全项目的地基：B 解析出来的、C 识别出来的、页面手动填的，最后都调这里的函数入库。
签名定了就不许改，改了另外三个人全崩。
"""

from __future__ import annotations

from app.constants import DEFAULT_CATEGORY, DIRECTION_EXPENSE, DIRECTIONS
from app.db.conn import now_str, tx


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
    raise NotImplementedError("TODO(A) 第 3-4 天：校验 + 入库")


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
    raise NotImplementedError("TODO(A) 第 3-4 天")


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
