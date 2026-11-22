"""生成示例账单数据（Owner: C｜第 3-4 天出 20 笔，第 9-10 天补到 120 笔）

为什么需要它：评审 clone 下来之后，必须**不用自己造数据**就能看到报表和预算告警。
没有它，统计页和预算页都是空的，等于没做。

⭐ 关键：日期用**相对今天的天数偏移**，不要写死 2026-11-01。
   否则过几个月再跑，数据全在"去年"，统计页一片空白。

产出：
    data/sample_transactions.csv   示例账单（可提交进仓库）
    然后可选地直接灌进数据库

用法：
    python scripts/generate_sample_data.py                 # 生成 120 笔 CSV
    python scripts/generate_sample_data.py --rows 20       # 第 3-4 天先出 20 笔
    python scripts/generate_sample_data.py --import        # 生成并灌库（幂等）
    python scripts/generate_sample_data.py --anchor 2026-11-21   # 固定基准日，便于复现
"""

from __future__ import annotations

import argparse
import calendar
import csv
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 把项目根目录加进 import 路径（必须在 import app.* 之前）。
# 不加这段：`python scripts/generate_sample_data.py` 时 sys.path[0] 是 scripts/，
# `--import` 会因为 import 不到 app 包而静默降级成"只生成 CSV"，很难查。
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_CSV = ROOT / "data" / "sample_transactions.csv"

# 每类消费的（金额区间 元, 权重, 商户示例）
RECIPES: dict[str, tuple[tuple[float, float], int, tuple[str, ...]]] = {
    "餐饮": ((12, 60), 40, ("沙县小吃", "食堂", "星巴克", "美团外卖", "兰州拉面", "奶茶店")),
    "交通": ((3, 45), 18, ("地铁", "公交", "滴滴", "共享单车", "高铁")),
    "购物": ((20, 300), 12, ("淘宝", "京东", "超市", "优衣库")),
    "娱乐": ((25, 120), 8, ("电影院", "KTV", "视频会员", "剧本杀")),
    "居住": ((300, 1200), 4, ("房租", "水电费", "物业费")),
    "医疗": ((15, 200), 3, ("药店", "校医院")),
    "教育": ((30, 400), 4, ("书店", "网课", "考试报名")),
    "通讯": ((30, 100), 3, ("话费充值", "流量包")),
    "人情": ((50, 500), 3, ("红包", "生日礼物", "份子钱")),
    "其他": ((5, 50), 5, ("杂项",)),
}

# 收入（10% 的行是收入，让"收支"筛选有东西可切）
INCOME_KINDS: tuple[tuple[str, str, tuple[float, float]], ...] = (
    ("工资", "公司", (5000, 9000)),
    ("退款", "淘宝", (20, 200)),
    ("兼职", "兼职", (100, 800)),
    ("红包", "朋友", (10, 200)),
)

TARGET_ROWS = 120
MONTHS_BACK = 3

# 超支演示场景（答辩/演示一定会点预算页）
FOOD_BUDGET_YUAN = 800.0      # 本月餐饮预算
TOTAL_BUDGET_YUAN = 3000.0    # 本月总预算
OVERSPEND_RATIO = 1.15        # 目标：餐饮花到预算的 115%

# 餐饮的用餐时段（让时间看起来像真的）
MEAL_HOURS = (7, 8, 11, 12, 12, 13, 18, 19, 19, 20)


def _shift_month(day: date, months: int) -> date:
    """往前/往后挪几个月，返回那个月的 1 号。"""
    year = day.year
    month = day.month + months
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)


def _month_end(day: date) -> date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def _all_days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _random_time(rng: random.Random, category: str) -> tuple[int, int, int]:
    """随机一个看起来真实的时分秒。餐饮按饭点，其它按白天。"""
    if category == "餐饮":
        hour = rng.choice(MEAL_HOURS)
    else:
        hour = rng.randint(9, 21)
    return hour, rng.randint(0, 59), rng.randint(0, 59)


def _money(rng: random.Random, low: float, high: float) -> float:
    """按分取整，避免 25.300000000000004 这种鬼数字。"""
    cents = rng.randint(int(low * 100), int(high * 100))
    return cents / 100


def _overspend_rows(anchor: date) -> list[dict]:
    """本月餐饮的"超支演示"3 笔：合计正好是预算的 115%。

    为什么要单独造而不靠随机：随机数据每次都不一样，
    演示时"餐饮刚好 115%"这个点必须每次都能复现。
    """
    target = round(FOOD_BUDGET_YUAN * OVERSPEND_RATIO, 2)   # 920.00
    parts = [328.00, 296.00, 296.00]
    assert round(sum(parts), 2) == target, "超支演示金额和 115% 对不上"

    month_start = anchor.replace(day=1)
    merchants = ("海底捞火锅", "食堂聚餐", "美团外卖")
    rows = []
    for i, (amount, merchant) in enumerate(zip(parts, merchants)):
        # 尽量分散在最近几天，但别掉到上个月去
        day = max(month_start, anchor - timedelta(days=i * 3))
        rows.append({
            "occurred_at": f"{day.isoformat()} {12 + i * 3:02d}:30:00",
            "amount": amount,
            "direction": "expense",
            "category": "餐饮",
            "subcategory": "聚餐",
            "merchant": merchant,
            "note": "预算演示：餐饮已超支 115%",
            "source": "manual",
        })
    return rows


def generate(anchor: date | None = None, rows: int = TARGET_ROWS) -> list[dict]:
    """生成示例账单。

    规则：
    1. 覆盖最近 3 个月（含本月），让"本月 vs 上月"的对比有数据
    2. 餐饮占比最高（这样饼图好看）
    3. 90% 支出 + 10% 收入
    4. 预置超支场景：本月"餐饮"正好花到预算的 115%
    5. 同一个 anchor 下结果完全可复现（随机种子 = anchor 的天序号）
    """
    anchor = anchor or date.today()
    rng = random.Random(anchor.toordinal())   # 同一天生成结果一样，方便复现问题

    total = max(rows, 5)
    latest_start = _shift_month(anchor, -(MONTHS_BACK - 1))
    days = _all_days(latest_start, anchor)
    earlier_days = [d for d in days if d.month != anchor.month]

    specials = _overspend_rows(anchor)
    records: list[dict] = []

    for _ in range(total - len(specials)):
        is_income = rng.random() < 0.10

        if is_income:
            subcategory, merchant, (low, high) = rng.choice(INCOME_KINDS)
            category = "其他" if subcategory != "红包" else "人情"
            amount = _money(rng, low, high)
            day = rng.choice(days)
            note = None
        else:
            category = rng.choices(
                list(RECIPES), weights=[meta[1] for meta in RECIPES.values()], k=1
            )[0]
            (low, high), _, merchants = RECIPES[category]
            merchant = rng.choice(merchants)
            amount = _money(rng, low, high)
            subcategory = None
            note = None
            day = rng.choice(days)

            # 本月餐饮已经被"超支演示"占满了，随机餐饮挪到更早的月份，
            # 否则总数超过 920，115% 这个演示点就不准了
            if category == "餐饮" and day.month == anchor.month and earlier_days:
                day = rng.choice(earlier_days)

            if category == "餐饮" and amount > 40:
                note = "和同事 AA"
            if category == "居住" and merchant == "房租":
                subcategory = "房租"

        hour, minute, second = _random_time(rng, category)
        records.append({
            "occurred_at": f"{day.isoformat()} {hour:02d}:{minute:02d}:{second:02d}",
            "amount": amount,
            "direction": "income" if is_income else "expense",
            "category": category,
            "subcategory": subcategory,
            "merchant": merchant,
            "note": note,
            "source": "manual",
        })

    records.extend(specials)

    # 按时间排序，seed_key 用"锚点日 + 内容"，同一锚点重复执行 key 不变
    records.sort(key=lambda r: r["occurred_at"])
    counters: dict[str, int] = {}
    for record in records:
        base = (f"gen-{anchor.isoformat()}-{record['occurred_at'][:10]}-"
                f"{record['category']}-{record['amount']:.2f}")
        counters[base] = counters.get(base, 0) + 1
        record["seed_key"] = f"{base}-{counters[base]}"

    return records


def write_csv(records: list[dict], path: Path = OUT_CSV) -> None:
    """写 CSV。列顺序固定，UTF-8 编码（不然 Windows 上会乱码）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "seed_key", "occurred_at", "amount", "direction", "category",
        "subcategory", "merchant", "note", "source",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    print(f"已生成 {len(records)} 条示例账单：{path}")


def _seed_budgets(anchor: date) -> None:
    """给本月写两条预算，预算页一打开就能看到"餐饮 115%"的红色告警。"""
    from app.db.conn import now_str, tx

    month = anchor.strftime("%Y-%m")
    rows = [(month, "", int(TOTAL_BUDGET_YUAN * 100)),
            (month, "餐饮", int(FOOD_BUDGET_YUAN * 100))]
    with tx() as conn:
        for month_, category, cents in rows:
            conn.execute(
                "INSERT OR IGNORE INTO budgets (month, category, amount, created_at)"
                " VALUES (?, ?, ?, ?)",
                (month_, category, cents, now_str()),
            )


def _exists(record: dict) -> bool:
    """按"时间+金额+类别+商户"判重，重复执行不会灌出双份数据。"""
    from app.db.conn import tx
    from app.money import to_cents

    with tx() as conn:
        row = conn.execute(
            "SELECT 1 FROM transactions"
            " WHERE occurred_at = ? AND amount = ? AND category = ?"
            "   AND COALESCE(merchant, '') = ?",
            (record["occurred_at"], to_cents(record["amount"]),
             record["category"], record["merchant"] or ""),
        ).fetchone()
    return row is not None


def import_into_db(records: list[dict], anchor: date | None = None) -> int:
    """把示例数据灌进数据库。返回实际写入条数。

    ⚠️ 依赖 A 的 add_transaction()。它还没实现时**不报错**，
       只提示一句"先只用 CSV"，保证这个脚本任何时候都能跑。
    """
    try:
        from app.services.ledger import add_transaction
    except Exception:
        add_transaction = None

    if add_transaction is None:
        print("⚠️ 没找到 A 的 add_transaction()，这次只生成 CSV。")
        return 0

    # 第一次在空目录跑时，三张表还不存在；建表是幂等的，先跑一遍再写预算
    from app.db.conn import init_db

    init_db()
    _seed_budgets(anchor or date.today())

    inserted = 0
    try:
        for record in records:
            if _exists(record):
                continue
            payload = {k: v for k, v in record.items() if k != "seed_key"}
            add_transaction(payload)
            inserted += 1
    except NotImplementedError:
        print("⚠️ A 的 add_transaction() 还没接通，这次只生成 CSV。")
        return 0

    print(f"已写入数据库 {inserted} 条（跳过了已存在的 {len(records) - inserted} 条）")
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="生成示例账单数据")
    parser.add_argument("--import", dest="do_import", action="store_true",
                        help="生成后直接写入数据库")
    parser.add_argument("--anchor", type=str, default=None,
                        help="固定基准日期 YYYY-MM-DD，便于复现演示")
    parser.add_argument("--rows", type=int, default=TARGET_ROWS, help="生成条数")
    args = parser.parse_args()

    anchor = datetime.strptime(args.anchor, "%Y-%m-%d").date() if args.anchor else date.today()
    print(f"基准日期：{anchor}（生成 {args.rows} 条，覆盖最近 {MONTHS_BACK} 个月）")

    records = generate(anchor=anchor, rows=args.rows)
    write_csv(records)

    # 打印一眼能核对的统计，省得自己去翻 CSV
    month = anchor.strftime("%Y-%m")
    this_month_food = sum(
        r["amount"] for r in records
        if r["direction"] == "expense" and r["category"] == "餐饮"
        and r["occurred_at"][:7] == month
    )
    print(f"本月餐饮合计：{this_month_food:.2f} 元"
          f"（预算 {FOOD_BUDGET_YUAN:.0f}，占 {this_month_food / FOOD_BUDGET_YUAN:.0%}）")
    print(f"收支分布：支出 {sum(r['direction'] == 'expense' for r in records)} 笔，"
          f"收入 {sum(r['direction'] == 'income' for r in records)} 笔")

    if args.do_import:
        import_into_db(records, anchor=anchor)


if __name__ == "__main__":
    main()
