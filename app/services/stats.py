"""消费统计（Owner: A｜第 7-8 天完成）

D 的统计页需要的数据全从这里出。所有数字必须由 SQL 算，不许在这里写死或估算。
"""

from __future__ import annotations


def get_stats(
    start: str,
    end: str,
    category: str | None = None,
) -> dict:
    """统计 [start, end] 区间的消费情况，返回：

    {
        "total": 1234.5,                 # 支出合计
        "count": 42,                     # 笔数
        "avg": 29.4,                     # 单笔平均
        "max_single": {"amount": 300, "merchant": "某某", "occurred_at": "..."},
        "by_category": [                 # 按金额倒序，D 画饼图直接用
            {"category": "餐饮", "amount": 600, "ratio": 0.49, "count": 20},
            ...
        ],
        "monthly_trend": [               # 按月聚合，D 画折线图
            {"month": "2026-09", "amount": 900},
            ...
        ],
    }

    注意：
    - 只统计 direction='expense'，收入不算进"消费"
    - ratio 是占比 0~1，保留 2 位小数
    - 没有数据时返回 total=0、空列表，不要抛异常（D 的页面会崩）
    - **金额字段返回的单位都是「元」**（total / avg / amount / max_single.amount）
      SQL 里在「分」上求和（整数，精确），最后统一 money.to_yuan() 转成元返回

    TODO(A) 第 7-8 天
    """
    raise NotImplementedError("TODO(A) 第 7-8 天")


def compare_months(month_a: str, month_b: str) -> dict:
    """两个月对比（加分项）：{"a": {...}, "b": {...}, "diff": {...}, "by_category": [...]}

    答辩时能讲"这个月比上月多花了 300，主要在餐饮"。
    做不完可以不做。
    """
    raise NotImplementedError("TODO(A) 加分项，可跳过")
