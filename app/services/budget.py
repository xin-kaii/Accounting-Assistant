"""预算与超支判定（Owner: A｜第 9 天完成）

对应考核 MVP 第 4 项。D 的预算页靠这里的数据画进度条和告警。
"""

from __future__ import annotations

from app.constants import (
    BUDGET_OVER_RATIO,
    BUDGET_WARN_RATIO,
    LEVEL_OK,
    LEVEL_OVER,
    LEVEL_WARN,
)


def set_budget(month: str, amount: float, category: str = "") -> None:
    """设置预算。同一个 (month, category) 重复设置就覆盖（UPSERT）。

    month    : 'YYYY-MM'
    category : '' 表示总预算，其它值为分类预算
    amount   : >= 0，**单位：元**（入库时用 money.to_cents() 转成分）

    注意：schema 里 category 用 '' 而不是 NULL，因为 SQLite 里 NULL != NULL，
          UNIQUE 约束拦不住重复插入。

    TODO(A) 第 9 天
    """
    raise NotImplementedError("TODO(A) 第 9 天")


def get_budgets(month: str) -> list[dict]:
    """查某月所有预算：[{"category": "餐饮", "amount": 800}, ...]"""
    raise NotImplementedError("TODO(A) 第 9 天")


def delete_budget(month: str, category: str = "") -> bool:
    """删一条预算。TODO(A) 第 9 天"""
    raise NotImplementedError("TODO(A) 第 9 天")


def check_budget(month: str) -> list[dict]:
    """查某月预算的执行情况，D 的预算页直接用它渲染。

    返回（没有设预算时返回空列表）：
    [
        {
            "category": "餐饮",      # '' 表示总预算
            "budget": 800,
            "spent": 920,
            "remain": -120,          # 负数就是超了
            "ratio": 1.15,           # 已用比例
            "level": "over",         # ok / warn / over
        },
    ]

    ⚠️ ratio 必须用「分」算：ratio = spent_cents / budget_cents，
       不要用转成元之后的浮点数算，否则"刚好 100%"会判错。

    level 判定（阈值在 constants.py）：
        ratio < 0.70            -> "ok"    绿灯
        0.70 <= ratio <= 1.00   -> "warn"  黄灯
        ratio > 1.00            -> "over"  红灯

    ⚠️ 边界要写清楚：刚好花 800/800 = 100%，算 warn 不算 over。
       答辩会问"刚好 100% 算不算超支"，答案是不算，超过才算。

    TODO(A) 第 9 天
    """
    raise NotImplementedError("TODO(A) 第 9 天")


def _judge_level(ratio: float) -> str:
    """已实现：给 D 的示例用。你实现 check_budget 时可以直接调它。"""
    if ratio > BUDGET_OVER_RATIO:
        return LEVEL_OVER
    if ratio >= BUDGET_WARN_RATIO:
        return LEVEL_WARN
    return LEVEL_OK
