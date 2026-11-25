"""B 第 3 天验收：mock_llm.parse_record。

两层验收：
1. 基础 10 句（任务板原验收线：至少 8/10，金额 + 类别都正确）
2. 金额边界 24 句（P0-1 补强：日期/订单/优惠/多金额/数量，必须全过）

运行方式（在仓库根目录、venv 下）：
    python -m tests.test_mock_parse
"""

from app.llm.mock_llm import parse_record


BASIC_CASES = [
    ("午饭25", 25.0, "餐饮", "最基础：金额+餐饮"),
    ("昨天打车32", 32.0, "交通", "相对时间：昨天"),
    ("前天超市买东西88", 88.0, "购物", "相对时间：前天"),
    ("晚饭花了30块", 30.0, "餐饮", "带“块”单位的金额"),
    ("地铁3号线花了4块", 4.0, "交通", "先抓“4块”，不能把“3号线”当金额"),
    ("房租2500", 2500.0, "居住", "大额、无单位"),
    ("看电影45", 45.0, "娱乐", "娱乐类"),
    ("买药36.5", 36.5, "医疗", "小数金额"),
    ("话费充值100", 100.0, "通讯", "通讯类"),
    ("星巴克三十多", None, "餐饮", "模糊金额：必须给 None，不能猜 30"),
]

AMOUNT_CASES = [
    ("11月20号充话费50", 50.0, "日期数字不能当金额"),
    ("2026年11月20号充话费50", 50.0, "年月日都要屏蔽"),
    ("2026-11-25 12:30 午饭25", 25.0, "日期时间都要屏蔽"),
    ("11/20 午饭25", 25.0, "短日期要屏蔽"),
    ("我住3楼，房租2500", 2500.0, "楼层不能当金额"),
    ("30分钟停车费5元", 5.0, "时长不能当金额"),
    ("3.5公里打车20", 20.0, "距离不能当金额"),
    ("2人餐199", 199.0, "人数不能当金额"),
    ("第3次消费25", 25.0, "序数不能当金额"),
    ("手机13800138000，话费50", 50.0, "手机号不能当金额"),
    ("电话138-0013-8000，话费50", 50.0, "带横线手机号不能当金额"),
    ("订单号202611250001，金额50", 50.0, "订单号不能当金额"),
    ("房间1203，房租2500", 2500.0, "房间号不能当金额"),
    ("1,000元房租", 1000.0, "千分位"),
    ("1.5万", 15000.0, "万单位"),
    ("25元×2", 50.0, "数量乘单价"),
    ("3元优惠券后实付25元", 25.0, "优惠券不能当实付"),
    ("原价100，打折后80", 80.0, "原价不能当实付"),
    ("满100减20，实付80", 80.0, "满减条件不能当实付"),
    ("满100减20", None, "没有实付就返回 None"),
    ("25元打车，给3元小费", None, "小费场景有歧义返回 None"),
    ("午饭25，打车30", None, "一条消息多笔返回 None"),
    ("午饭25，打车30，一共55", 55.0, "有“一共”就取总额"),
    ("星巴克三十多", None, "中文模糊金额不猜"),
]


def run_basic() -> int:
    passed = 0
    print(f"{'输入':<18}{'金额':<10}{'类别':<8}{'判定':<6}说明")
    print("-" * 76)
    for text, expected_amount, expected_category, note in BASIC_CASES:
        record = parse_record(text)
        ok = record["amount"] == expected_amount and record["category"] == expected_category
        passed += int(ok)
        print(
            f"{text:<18}{str(record['amount']):<10}{record['category']:<8}"
            f"{'PASS' if ok else 'FAIL':<6}{note}"
        )
        if not ok:
            print(
                f"    期望 amount={expected_amount}, category={expected_category}；"
                f"实际 amount={record['amount']}, category={record['category']}"
            )
    print(f"基础 10 句：{passed}/10（验收线 8/10）")
    return passed


def run_amount_edges() -> int:
    passed = 0
    print(f"\n{'输入':<22}{'金额':<10}{'判定':<6}说明")
    print("-" * 76)
    for text, expected_amount, note in AMOUNT_CASES:
        record = parse_record(text)
        ok = record["amount"] == expected_amount
        passed += int(ok)
        print(
            f"{text:<22}{str(record['amount']):<10}"
            f"{'PASS' if ok else 'FAIL':<6}{note}"
        )
        if not ok:
            print(f"    期望 amount={expected_amount}；实际 amount={record['amount']}")
    print(f"金额边界 {len(AMOUNT_CASES)} 句：{passed}/{len(AMOUNT_CASES)}（必须全过）")
    return passed


def main() -> None:
    basic_passed = run_basic()
    edges_passed = run_amount_edges()
    print("-" * 76)
    if basic_passed < 8:
        print("基础验收未达标")
        raise SystemExit(1)
    if edges_passed < len(AMOUNT_CASES):
        print("金额边界未全过")
        raise SystemExit(1)
    print("全部通过")


if __name__ == "__main__":
    main()