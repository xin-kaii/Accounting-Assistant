"""B 第 3 天验收：mock_llm.parse_record（pytest 版）

三层验收，共 50 句：
1. 基础 10 句：金额 + 类别都对（任务板原验收线 8/10，现在要求全过）
2. 金额边界 24 句：日期/订单号/优惠券/多金额/数量的干扰，不能误抓
3. 方向 16 句：工资/报销/退款等收入判断，以及「退款失败，午饭25」这类反向用例

运行（仓库根目录、venv 下）：
    python -m pytest tests/test_mock_parse.py -v

函数名统一用 test_ 前缀，pytest 才会收集。
"""

from __future__ import annotations

import pytest

from app.llm.mock_llm import parse_record

# 返回结构必须齐全的 9 个字段（和 B 的 parse_record、C 的 extract_receipt 对齐）
FIELDS = (
    "amount",
    "direction",
    "category",
    "subcategory",
    "merchant",
    "note",
    "occurred_at",
    "confidence",
    "missing_fields",
)

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

DIRECTION_CASES = [
    ("工资5000", 5000.0, "income", "工资是收入"),
    ("本月工资到账5000", 5000.0, "income", "工资到账"),
    ("收入5000", 5000.0, "income", "收入"),
    ("报销200", 200.0, "income", "报销"),
    ("退款30", 30.0, "income", "退款"),
    ("退回押金200", 200.0, "income", "退回押金是收入"),
    ("奖金1000", 1000.0, "income", "奖金"),
    ("利息20", 20.0, "income", "利息"),
    ("收到红包200", 200.0, "income", "收到红包"),
    ("发红包200", 200.0, "expense", "发红包是支出"),
    ("午饭25", 25.0, "expense", "默认支出"),
    ("退款失败，午饭25", 25.0, "expense", "退款失败不能当收入"),
    ("工资条打印，午饭25", 25.0, "expense", "工资条不是一笔收入"),
    ("报销流程说明，午饭25", 25.0, "expense", "报销流程不是一笔收入"),
    ("收到红包200，买咖啡25", 25.0, "expense", "方向跟着选中的金额，不跟全句关键词"),
    ("工资5000，买咖啡25", 25.0, "expense", "有工资也有支出，选中的是咖啡"),
]


@pytest.mark.parametrize("text,expected_amount,expected_category,note", BASIC_CASES)
def test_basic(text, expected_amount, expected_category, note):
    record = parse_record(text)
    assert record["amount"] == expected_amount, f"{note}：期望 {expected_amount}，实际 {record['amount']}"
    assert record["category"] == expected_category, (
        f"{note}：期望 {expected_category}，实际 {record['category']}"
    )


@pytest.mark.parametrize("text,expected_amount,note", AMOUNT_CASES)
def test_amount_edge(text, expected_amount, note):
    record = parse_record(text)
    assert record["amount"] == expected_amount, f"{note}：期望 {expected_amount}，实际 {record['amount']}"


@pytest.mark.parametrize("text,expected_amount,expected_direction,note", DIRECTION_CASES)
def test_direction(text, expected_amount, expected_direction, note):
    record = parse_record(text)
    assert record["amount"] == expected_amount, f"{note}：期望 {expected_amount}，实际 {record['amount']}"
    assert record["direction"] == expected_direction, (
        f"{note}：期望 {expected_direction}，实际 {record['direction']}"
    )


@pytest.mark.parametrize("text", ["午饭25", "发工资8000", "星巴克三十多"])
def test_return_structure(text):
    """不管走哪条路，9 个字段一个都不能少——页面只认这一套。"""
    record = parse_record(text)
    missing = [f for f in FIELDS if f not in record]
    assert not missing, f"{text} 缺字段：{missing}"


def test_missing_amount_recorded():
    """金额抓不到时，必须写进 missing_fields，页面据此让用户补。"""
    record = parse_record("星巴克三十多")
    assert record["amount"] is None
    assert "amount" in record["missing_fields"]
