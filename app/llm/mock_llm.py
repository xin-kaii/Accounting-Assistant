"""离线规则模式（Owner: B｜第 3 天就要有，优先级最高）

为什么必须有：
1. 评审可能没网、没配 Key、额度用完了 —— 有它，演示永不翻车
2. 对手 KuGua-Gu 已经做了（他们的 mock_llm.py），我们不做吃亏
3. 写测试时不用花钱调模型

设计原则：只覆盖"能演示"的最小场景，不追求效果。
    "午饭 25"                -> 金额 25，类别 餐饮
    "昨天打车 32"            -> 金额 32，类别 交通，时间昨天
    "上个月吃饭花了多少"      -> {时间段: 上月, 类别: 餐饮, 指标: 合计}

已知做不到（也没必要做）：口语化的复杂句子、一条消息多笔。
在这些情况返回 confidence 低 + missing_fields 非空，让页面走"人工确认"。
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from app.constants import DEFAULT_CATEGORY

# ---------- 关键词表（够演示就行，不用穷举）----------
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "餐饮": ("饭", "午饭", "晚饭", "早饭", "早餐", "午餐", "晚餐", "吃", "咖啡",
             "奶茶", "外卖", "食堂", "烧烤", "火锅", "面", "米饭", "水果"),
    "交通": ("打车", "出租车", "地铁", "公交", "高铁", "火车", "机票", "加油",
             "停车", "单车", "滴滴"),
    "购物": ("买", "淘宝", "京东", "拼多多", "超市", "衣服", "鞋", "耳机", "数码"),
    "娱乐": ("电影", "游戏", "KTV", "唱歌", "会员", "演唱会", "剧本杀"),
    "居住": ("房租", "水电", "物业", "宽带", "燃气"),
    "医疗": ("药", "医院", "挂号", "体检", "牙"),
    "教育": ("书", "课程", "学费", "考试", "培训"),
    "通讯": ("话费", "流量", "充值"),
    "人情": ("红包", "份子", "礼物", "随礼"),
}

# 金额：25、25.5、25元、￥25、25块
AMOUNT_RE = re.compile(r"(\d+(?:\.\d{1,2})?)\s*(?:元|块|rmb|￥|¥)?", re.IGNORECASE)
# 明确带单位的金额优先（避免把"3号线"识别成 3 元）
AMOUNT_STRICT_RE = re.compile(r"(?:￥|¥)?\s*(\d+(?:\.\d{1,2})?)\s*(?:元|块)")


def parse_record(text: str) -> dict:
    """离线版 parse_record。返回结构和 B 的正式版完全一致。

    TODO(B) 第 3 天。实现提示：
        1. 先用 AMOUNT_STRICT_RE 抓带单位的金额，抓不到再用 AMOUNT_RE
        2. 用 CATEGORY_KEYWORDS 扫关键词定类别，一个都没中就 DEFAULT_CATEGORY
        3. 时间：含"昨天"就 today-1；含"前天"就 -2；都没有就用今天
        4. 金额抓不到 -> amount=None，missing_fields 里加 "amount"
        5. confidence 按"金额和类别都抓到了 = 0.9，缺一个 = 0.5"给
    """
        # ① 抓金额：先抓带单位的，抓不到再抓裸数字
    m = AMOUNT_STRICT_RE.search(text)
    if m is None:
        m = AMOUNT_RE.search(text)
    amount = float(m.group(1)) if m else None

    # ② 定类别：扫关键词表
    category = DEFAULT_CATEGORY
    hit_keyword = False
    for cat, words in CATEGORY_KEYWORDS.items():
        if any(w in text for w in words):
            category = cat
            hit_keyword = True
            break

    # ③ 定时间：昨天/前天/今天
    now = datetime.now()
    if "前天" in text:
        day = now - timedelta(days=2)
    elif "昨天" in text:
        day = now - timedelta(days=1)
    else:
        day = now

    # ④ 缺金额就记下来
    missing = []
    if amount is None:
        missing.append("amount")

    # ⑤ 置信度
    confidence = 0.9 if (amount is not None and hit_keyword) else 0.5

    # 组装 9 个字段返回
    return {
        "amount": amount,
        "direction": "expense",
        "category": category,
        "subcategory": None,
        "merchant": None,
        "note": None,
        "occurred_at": day.strftime("%Y-%m-%d 00:00:00"),
        "confidence": confidence,
        "missing_fields": missing,
    }



def classify(text: str) -> tuple[str, float]:
    """离线版分类。返回 (类别, 置信度)。关键词命中越多置信度越高。"""
    raise NotImplementedError("TODO(B) 第 3 天")


def parse_query(text: str) -> dict:
    """离线版查账解析。

    返回 {"metric": "sum"|"rank"|"count",
          "time_start": "YYYY-MM-DD", "time_end": "YYYY-MM-DD",
          "category": "餐饮"|None, "direction": "expense"}

    TODO(B) 第 7-8 天。实现提示：
        1. "上月/上个月" -> 上个月 1 号到月底；"本月/这个月" -> 本月
        2. "最近30天" -> today-30 到 today
        3. 类别用 CATEGORY_KEYWORDS 扫
        4. "哪类/最多/排行" -> metric="rank"；"多少/花了多少" -> "sum"
        5. 认不出来就抛 ValueError，让页面提示"没听懂，换个说法"
    """
    raise NotImplementedError("TODO(B) 第 7-8 天")
