"""生成示例账单数据（Owner: C｜第 3-4 天出 20 笔，第 9-10 天补到 120 笔）

为什么需要它：评审 clone 下来之后，必须**不用自己造数据**就能看到报表和预算告警。
没有它，统计页和预算页都是空的，等于没做。

⭐ 关键：日期用**相对今天的天数偏移**，不要写死 2026-11-01。
   否则过几个月再跑，数据全在"去年"，统计页一片空白。

产出：
    data/sample_transactions.csv   示例账单（可提交进仓库）
    然后可选地直接灌进数据库

用法：
    python scripts/generate_sample_data.py            # 只生成 CSV
    python scripts/generate_sample_data.py --import   # 生成并灌库
    python scripts/generate_sample_data.py --anchor 2026-11-21   # 固定基准日，便于复现
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = ROOT / "data" / "sample_transactions.csv"

# 每类消费的（金额区间, 权重, 商户示例）
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

TARGET_ROWS = 120
MONTHS_BACK = 3


def generate(anchor: date | None = None, rows: int = TARGET_ROWS) -> list[dict]:
    """生成示例账单。

    要求：
    1. 覆盖最近 3 个月（含本月），让"本月 vs 上月"的对比有数据
    2. 大约 120 笔，餐饮占比最高（这样饼图好看）
    3. 90% 支出 + 10% 收入（收入用来让"收支"筛选有东西可切）
    4. **必须预置一个超支场景**：让本月"餐饮"的预算花到 115%，
       这样预算页一打开就能看到红色告警（评审一定会点这一页）
    5. 每条都有一个稳定的 seed_key（比如 "gen-2026-11-20-餐饮-25.0"），
       重复执行不会插重复数据

    TODO(C) 第 3-4 天先做 20 笔，第 9-10 天补到 120 笔
    """
    raise NotImplementedError("TODO(C) 第 3-4 天")


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

    if args.do_import:
        # TODO(C)：调 A 的 add_transaction() 逐条入库，
        # 已存在相同 seed_key 的跳过（幂等）
        raise NotImplementedError("TODO(C)：幂等导入")


if __name__ == "__main__":
    main()
