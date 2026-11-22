"""B 第 3 天验收：mock_llm.parse_record 的 10 句测试。

验收标准：10 句里至少 8 句的 amount（金额）和 category（类别）同时正确。
运行方式（在仓库根目录）：
    python -m tests.test_mock_parse

每条用例 = (输入句子, 期望金额, 期望类别, 备注)。
金额单位是元；"三十多"这种没给准确数字的，期望是 None（不猜）。
"""

from app.llm.mock_llm import parse_record


CASES = [
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


def main() -> None:
    passed = 0
    print(f"{'输入':<16}{'金额':<10}{'类别':<8}{'判定':<6}说明")
    print("-" * 70)
    for text, expected_amount, expected_category, note in CASES:
        record = parse_record(text)
        amount_ok = record["amount"] == expected_amount
        category_ok = record["category"] == expected_category
        ok = amount_ok and category_ok
        passed += int(ok)

        result = "PASS" if ok else "FAIL"
        print(
            f"{text:<16}{str(record['amount']):<10}{record['category']:<8}"
            f"{result:<6}{note}"
        )
        if not ok:
            print(
                f"    期望 amount={expected_amount}, category={expected_category}；"
                f"实际 amount={record['amount']}, category={record['category']}"
            )

    total = len(CASES)
    print("-" * 70)
    print(f"通过 {passed}/{total}，验收线是 8/{total}：{'达标' if passed >= 8 else '未达标'}")

    if passed < 8:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
