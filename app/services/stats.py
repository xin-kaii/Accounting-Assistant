"""消费统计（Owner: A｜第 7-8 天完成）

统计页需要的数据全从这里出。所有数字必须由 SQL 算，不许在这里写死或估算。
"""

from __future__ import annotations

from app.dates import parse_day
from app.db.conn import tx
from app.money import to_yuan


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
        "by_category": [                 # 按金额倒序，页面画饼图直接用
            {"category": "餐饮", "amount": 600, "ratio": 0.49, "count": 20},
            ...
        ],
        "monthly_trend": [               # 按月聚合，页面画折线图
            {"month": "2026-09", "amount": 900},
            ...
        ],
    }

    注意：
    - 只统计 direction='expense'，收入不算进"消费"
    - ratio 是占比 0~1，保留 2 位小数
    - 没有数据时返回 total=0、空列表，不要抛异常（统计页会崩）
    - **金额字段返回的单位都是「元」**（total / avg / amount / max_single.amount）
      SQL 里在「分」上求和（整数，精确），最后统一 money.to_yuan() 转成元返回
    - category 传 None / 空串表示不筛（和 list_transactions 同一套约定）
    - start 晚于 end 时抛 ValueError（和 list_transactions 一致，不静默返回空）
    - max_single 在区间内一笔支出都没有时返回 None，页面要判空
    """
    start = parse_day(start, "start")
    end = parse_day(end, "end")
    # 反区间不报错的话会静默返回"0 元"，看起来像这个月没花钱——和 ledger 一样直接抛
    if start > end:
        raise ValueError(f"start 不能晚于 end：{start!r} > {end!r}")

    # 闭区间，和 list_transactions 完全同一套口径：
    # start 从当天 00:00:00 起，end 到当天 23:59:59 止。
    # occurred_at 是归一化过的 'YYYY-MM-DD HH:MM:SS' 文本，字符串比较 = 时间比较。
    start_full = f"{start} 00:00:00"
    end_full = f"{end} 23:59:59"

    # WHERE 片段拼在 f-string 里，但**值全部走 ? 占位符**——
    # 拼进去的只有我们写死的固定文字，用户的输入永远不进 SQL 字符串。
    where = "direction = 'expense' AND occurred_at >= ? AND occurred_at <= ?"
    params: list[object] = [start_full, end_full]
    if category is not None and str(category).strip():
        where += " AND category = ?"
        params.append(str(category).strip())

    with tx() as conn:
        # 1) 总额 / 笔数：一条聚合 SQL 就够。
        #    SUM 在「分」（整数）上累加，120 笔也不会有浮点误差。
        total_row = conn.execute(
            f"""SELECT COUNT(*) AS cnt, COALESCE(SUM(amount), 0) AS cents
                FROM transactions WHERE {where}""",
            params,
        ).fetchone()

        # 2) 单笔最高：按金额倒序取第一行，顺带把它的商户和时间带出来。
        #    并列最高时按 id 再排一次，结果才是确定的（否则测试断言具体商户会偶发失败）。
        max_row = conn.execute(
            f"""SELECT amount, merchant, occurred_at
                FROM transactions WHERE {where}
                ORDER BY amount DESC, id DESC LIMIT 1""",
            params,
        ).fetchone()

        # 3) 分类占比：GROUP BY 后在 SQL 里排好序（金额倒序），页面直接喂饼图。
        cat_rows = conn.execute(
            f"""SELECT category, SUM(amount) AS cents, COUNT(*) AS cnt
                FROM transactions WHERE {where}
                GROUP BY category
                ORDER BY cents DESC""",
            params,
        ).fetchall()

        # 4) 月度趋势：occurred_at 的前 7 位就是 'YYYY-MM'。
        #    敢这么截是因为入库时格式已归一化（ledger._parse_occurred_at），
        #    这也是「时间必须统一格式入库」换来的好处。
        month_rows = conn.execute(
            f"""SELECT substr(occurred_at, 1, 7) AS month, SUM(amount) AS cents
                FROM transactions WHERE {where}
                GROUP BY substr(occurred_at, 1, 7)
                ORDER BY month""",
            params,
        ).fetchall()

    total_cents = int(total_row["cents"])
    count = int(total_row["cnt"])

    max_single = None
    if max_row is not None:
        max_single = {
            "amount": to_yuan(max_row["amount"]),
            "merchant": max_row["merchant"],  # 可能为 None，页面显示时兜底
            "occurred_at": max_row["occurred_at"],
        }

    by_category = [
        {
            "category": row["category"],
            "amount": to_yuan(row["cents"]),
            # 两个 int 相除再 round，ratio 也是精确的
            "ratio": round(row["cents"] / total_cents, 2) if total_cents else 0.0,
            "count": int(row["cnt"]),
        }
        for row in cat_rows
    ]

    monthly_trend = [
        {"month": row["month"], "amount": to_yuan(row["cents"])}
        for row in month_rows
    ]

    return {
        "total": to_yuan(total_cents),
        "count": count,
        # 平均值先在「分」上四舍五入到整分，再转元；count=0 时给 0，不能除零
        "avg": to_yuan(round(total_cents / count)) if count else 0.0,
        "max_single": max_single,
        "by_category": by_category,
        "monthly_trend": monthly_trend,
    }


def compare_months(month_a: str, month_b: str) -> dict:
    """两个月对比（加分项）：{"a": {...}, "b": {...}, "diff": {...}, "by_category": [...]}

    答辩时能讲"这个月比上月多花了 300，主要在餐饮"。
    做不完可以不做。
    """
    raise NotImplementedError("TODO(A) 加分项，可跳过")
