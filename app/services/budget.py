"""预算与超支判定（Owner: A｜第 9 天完成）

对应考核 MVP 第 4 项。预算页靠这里的数据画进度条和告警。
"""

from __future__ import annotations

from datetime import datetime

from app.constants import (
    BUDGET_OVER_RATIO,
    BUDGET_WARN_RATIO,
    CATEGORIES,
    LEVEL_OK,
    LEVEL_OVER,
    LEVEL_WARN,
)
from app.db.conn import MONTH_FMT, now_str, tx
from app.money import to_cents, to_yuan


def _parse_month(month: object) -> str:
    """month 只认 'YYYY-MM'。和日期一样：口径错了宁可报错，不要静默查空。"""
    text = str(month or "").strip()
    try:
        datetime.strptime(text, MONTH_FMT)
    except ValueError:
        raise ValueError(f"month 必须是 'YYYY-MM'，收到 {month!r}") from None
    return text


def _parse_category(category: object) -> str:
    """预算的类别：'' 表示总预算，其余必须是 10 个固定分类之一。

    ⚠️ 注意和 ledger._clean_text 的区别：那边把空白字符串洗成 NULL，
    这边 '' 是**一个有意义的值**（总预算），洗掉就没人设得了总预算了。
    """
    text = str(category or "").strip()
    if text and text not in CATEGORIES:
        raise ValueError(f"category 必须是 {CATEGORIES} 或 ''（总预算），收到 {category!r}")
    return text


def _parse_amount(amount: object) -> int:
    """预算允许 0（= 这项不打算花钱），但不允许负数和非法值。元 -> 分。"""
    try:
        yuan = float(amount)
    except (TypeError, ValueError):
        raise ValueError(f"amount 必须是数字，收到 {amount!r}") from None
    if yuan < 0:
        raise ValueError(f"amount 不能是负数，收到 {yuan}")
    return to_cents(yuan)


def set_budget(month: str, amount: float, category: str = "") -> None:
    """设置预算。同一个 (month, category) 重复设置就覆盖（UPSERT）。

    month    : 'YYYY-MM'
    category : '' 表示总预算，其它值为分类预算
    amount   : >= 0，**单位：元**（入库时用 money.to_cents() 转成分）

    注意：schema 里 category 用 '' 而不是 NULL，因为 SQLite 里 NULL != NULL，
          UNIQUE 约束拦不住重复插入。
    """
    month = _parse_month(month)
    category = _parse_category(category)
    cents = _parse_amount(amount)

    with tx() as conn:
        # UPSERT：撞上 UNIQUE(month, category) 约束时不报错，改成更新那条的 amount。
        # 用 DO UPDATE 而不是 INSERT OR REPLACE：
        #   REPLACE 是「先删旧行再插新行」，id 和 created_at 都会变；
        #   DO UPDATE 只改 amount，第一次设置的时间保留下来。
        conn.execute(
            """
            INSERT INTO budgets (month, category, amount, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(month, category) DO UPDATE SET amount = excluded.amount
            """,
            (month, category, cents, now_str()),
        )


def get_budgets(month: str) -> list[dict]:
    """查某月所有预算：[{"category": "餐饮", "amount": 800}, ...]

    category 为 '' 表示总预算（'' 比任何非空字符串都小，ASC 排序天然排最前）。
    amount 返回「元」，和设置时单位一致。
    """
    month = _parse_month(month)
    with tx() as conn:
        rows = conn.execute(
            "SELECT category, amount FROM budgets WHERE month = ? ORDER BY category",
            (month,),
        ).fetchall()
    return [{"category": row["category"], "amount": to_yuan(row["amount"])} for row in rows]


def delete_budget(month: str, category: str = "") -> bool:
    """删一条预算。记录不存在返回 False。

    因为入库时 category 存的是 '' 而不是 NULL，这里普通的 = 就能匹配；
    如果当初存了 NULL，就得写 category IS NULL（NULL 和 NULL 不相等）。
    """
    month = _parse_month(month)
    category = str(category or "").strip()
    with tx() as conn:
        cur = conn.execute(
            "DELETE FROM budgets WHERE month = ? AND category = ?",
            (month, category),
        )
        return cur.rowcount > 0


def check_budget(month: str) -> list[dict]:
    """查某月预算的执行情况，预算页直接用它渲染。

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

    level 判定（阈值在 constants.py，判定用 _judge_level，比例取原始值不先 round）：
        ratio < 0.70            -> "ok"    绿灯
        0.70 <= ratio <= 1.00   -> "warn"  黄灯
        ratio > 1.00            -> "over"  红灯

    ⚠️ 边界要写清楚：刚好花 800/800 = 100%，算 warn 不算 over。
       答辩会问"刚好 100% 算不算超支"，答案是不算，超过才算。
       （10000 分预算花 10000 分 -> ratio 恰好 1.0 -> warn；
        花 10001 分 -> ratio = 1.0001 -> round 成 1.0 但 level 是 over ——
        所以 level 必须在 round 之前判定，任务板的边界测试就是这么设计的）

    特殊情况：预算设了 0 元且该类有支出 -> ratio = inf（无限超支），
    level 照常判 over；页面显示时要注意 inf 不能直接放进进度条。
    """
    month = _parse_month(month)

    with tx() as conn:
        budget_rows = conn.execute(
            "SELECT category, amount FROM budgets WHERE month = ?",
            (month,),
        ).fetchall()
        if not budget_rows:
            return []

        # 该月每个分类的已花金额（只算支出）。
        # 没花过钱的分类不会出现在 GROUP BY 结果里，下面用 .get(…, 0) 兜成 0。
        spent_rows = conn.execute(
            """SELECT category, SUM(amount) AS cents
               FROM transactions
               WHERE direction = 'expense' AND substr(occurred_at, 1, 7) = ?
               GROUP BY category""",
            (month,),
        ).fetchall()

    spent_by_category = {row["category"]: int(row["cents"]) for row in spent_rows}
    # 总预算的「已花」= 该月所有支出（含没设预算的分类），不是各类预算的加和
    total_spent_cents = sum(spent_by_category.values())

    result = []
    for row in budget_rows:
        category = row["category"]
        budget_cents = int(row["amount"])
        spent_cents = (
            total_spent_cents if category == "" else spent_by_category.get(category, 0)
        )

        if budget_cents > 0:
            ratio = spent_cents / budget_cents    # 分 / 分，整数除整数，边界精确
        else:
            ratio = 0.0 if spent_cents == 0 else float("inf")

        result.append(
            {
                "category": category,
                "budget": to_yuan(budget_cents),
                "spent": to_yuan(spent_cents),
                "remain": to_yuan(budget_cents - spent_cents),
                "ratio": round(ratio, 2),
                "level": _judge_level(ratio),  # 用原始比例判定，round 只影响显示
            }
        )

    # 总预算排最前，其余按已用比例从高到低（最危险的最先看到）
    total = [r for r in result if r["category"] == ""]
    others = sorted((r for r in result if r["category"] != ""), key=lambda r: -r["ratio"])
    return total + others


def _judge_level(ratio: float) -> str:
    """给页面的示例用。你实现 check_budget 时可以直接调它。"""
    if ratio > BUDGET_OVER_RATIO:
        return LEVEL_OVER
    if ratio >= BUDGET_WARN_RATIO:
        return LEVEL_WARN
    return LEVEL_OK
