"""离线规则模式（Owner: B｜第 3 天就要有，优先级最高）

为什么必须有：
1. 评审可能没网、没配 Key、额度用完了 —— 有它，演示永不翻车
2. 对手 KuGua-Gu 已经做了（他们的 mock_llm.py），我们不做吃亏
3. 写测试时不用花钱调模型

设计原则：覆盖"能演示 + 常见记账说法"，但不追求自然语言全对。
    "午饭 25"                -> 金额 25，类别 餐饮
    "昨天打车 32"            -> 金额 32，类别 交通，时间昨天
    "11月20号充话费50"       -> 金额 50（11月/20号不是金额）
    "3元券后实付25元"        -> 金额 25（不拿券当实付）

已知做不到（mock 的边界，遇到就返回 None 或低置信度，让页面人工确认）：
- 中文数字/模糊数：三十、两百、一万五
- 元角分混合：25元5角、1块5
- 单价×人数/份数写在后面：25元/人，2人；25元一份，买2份
- 只给原价+折扣、不给实付：100元打8折
- 一条消息多笔：午饭25，打车30
- 万/千简写：3万5（当前只认 3万，不认后面的 5 千）
- 绝对日期：11月20号 只用于屏蔽金额，occurred_at 仍按今天
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from app.constants import DEFAULT_CATEGORY

# ---------- 关键词表（够演示就行，不用穷举）----------
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "餐饮": ("饭", "午饭", "晚饭", "早饭", "早餐", "午餐", "晚餐", "吃", "咖啡", "星巴克",
             "奶茶", "外卖", "食堂", "烧烤", "火锅", "面", "米饭", "水果"),
    "交通": ("打车", "出租车", "地铁", "公交", "高铁", "火车", "机票", "加油",
             "停车", "单车", "滴滴"),
    "购物": ("淘宝", "京东", "拼多多", "超市", "衣服", "鞋", "耳机", "数码"),
    "娱乐": ("电影", "游戏", "KTV", "唱歌", "会员", "演唱会", "剧本杀"),
    "居住": ("房租", "水电", "物业", "宽带", "燃气"),
    "医疗": ("药", "医院", "挂号", "体检", "牙"),
    "教育": ("书", "课程", "学费", "考试", "培训"),
    "通讯": ("话费", "流量", "充值"),
    "人情": ("红包", "份子", "礼物", "随礼"),
}

# 金额候选：25、25.5、25元、￥25、25块、1,000、1.5万
AMOUNT_CANDIDATE_RE = re.compile(
    r"(?P<prefix>￥|¥)?\s*"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"\s*(?P<mult>万|千)?\s*(?P<unit>元|块|rmb)?",
    re.IGNORECASE,
)

# 不是金额的数字：日期、时间、电话/订单/房间号、楼层/线路/数量等
DATE_RE = re.compile(
    r"(?<!\d)(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/]\d{1,2})(?!\d)"
)
TIME_RE = re.compile(r"\d{1,2}:\d{2}")
MULT_SPACE_RE = re.compile(r"([×*xX])\s+")
ID_PREFIX_RE = re.compile(
    r"(?:验证码|订单号|单号|编号|手机号码|手机号|手机|电话号码|电话|"
    r"身份证号码|身份证号|身份证|银行卡号|卡号|账号|房间号|房号|房间|学号|工号)"
    r"\s*[:：]?\s*\d[\d-]*"
)
LONG_NUMBER_RE = re.compile(
    r"(?<!\d)\d{8,}(?:\.\d+)?(?!\d|\s*(?:元|块|rmb))",
    re.IGNORECASE,
)
ORDINAL_RE = re.compile(r"第\s*\d+(?:\.\d+)?")
NON_AMOUNT_RE = re.compile(
    r"(?<![×*xX])\d+(?:\.\d+)?\s*(?:"
    r"号线|号楼|单元|分钟|小时|公里|公斤|千克|厘米|毫米|毫升|个月|"
    r"月|日|号|楼|层|室|厅|栋|幢|路|站|岁|点|个|杯|人|位|天|年|次|折|"
    r"斤|克|米|寸|码|升|包|袋|箱|瓶|件|套|双|张|本|支|台|部|辆|秒|分|份|盒|碗|盘|串|只|条|根|颗|粒|片|听|罐|%"
    r")"
)

# 金额选择：只有一个候选就用；多个候选只认明确指向“实际支付”的那个
ACTUAL_CUES = (
    "实付", "付了", "付款", "支付", "花了", "花", "一共", "总共", "合计",
    "消费", "充值", "充", "券后", "优惠后", "折后", "现价", "到手价", "买", "交", "缴",
)
NEGATIVE_CUES = ("原价", "优惠", "券", "小费", "押金", "定金")
NEGATIVE_EDGE_CUES = ("满", "减", "省")


def _mask_non_amounts(text: str) -> str:
    """把日期、时间、证件/订单号、楼层/线路/数量等数字替换成空格。

    只用于金额提取，不改原文；否则类别、时间、备注会被破坏。
    """
    masked = MULT_SPACE_RE.sub(r"\1", text)
    masked = DATE_RE.sub(" ", masked)
    masked = TIME_RE.sub(" ", masked)
    masked = ID_PREFIX_RE.sub(" ", masked)
    masked = LONG_NUMBER_RE.sub(" ", masked)
    masked = ORDINAL_RE.sub(" ", masked)
    masked = NON_AMOUNT_RE.sub(" ", masked)
    return masked


def _extract_amount(text: str) -> float | None:
    """从一句话里选一个金额；多个候选且没有“实付”等明确线索时返回 None。

    mock 的原则：宁可不猜，也不把优惠券、原价、日期当成实际金额。
    """
    amount_text = _mask_non_amounts(text)
    candidates = []
    ignore_until = -1
    for m in AMOUNT_CANDIDATE_RE.finditer(amount_text):
        if m.start() < ignore_until:
            continue
        value = float(m.group("num").replace(",", ""))
        mult = m.group("mult")
        if mult == "万":
            value *= 10000
        elif mult == "千":
            value *= 1000
        # 25元×2 / 25元*2 / 25元x2 -> 50
        qty = re.match(r"\s*[×*xX]\s*(\d+)", amount_text[m.end():m.end() + 8])
        if qty:
            value *= int(qty.group(1))
            ignore_until = m.end() + qty.end()
        value = round(value, 2)
        has_unit = bool(m.group("prefix") or m.group("unit") or mult)
        before = amount_text[max(0, m.start() - 4):m.start()]
        after = amount_text[m.end():m.end() + 4]
        actual = any(cue in before for cue in ACTUAL_CUES)
        negative = any(cue in before for cue in NEGATIVE_CUES) or any(
            cue in after for cue in NEGATIVE_CUES
        ) or any(before.endswith(cue) for cue in NEGATIVE_EDGE_CUES)
        score = (3 if has_unit else 0) + (4 if actual else 0) - (2 if negative else 0)
        candidates.append((value, score, actual, negative))

    if not candidates:
        return None
    # 句子里只有优惠/原价/小费，没有任何“实付”类线索：宁可不猜
    if not any(c[2] for c in candidates) and any(c[3] for c in candidates):
        return None

    best_score = max(c[1] for c in candidates)
    best = [c for c in candidates if c[1] == best_score]
    if len(best) > 1 and len({c[0] for c in best}) > 1:
        return None
    chosen = best[0]
    if chosen[3] and not chosen[2]:
        return None
    return chosen[0]


def parse_record(text: str) -> dict:
    """离线版 parse_record。返回结构和 B 的正式版完全一致。

    金额策略：
        1. 先屏蔽日期、时间、订单/电话/房间号、楼层/线路/数量等非金额数字
        2. 从剩余候选里选“实际支付”：只有一个候选就用；多个候选优先“实付/花了/充值”等线索
        3. 多个候选且没有明确线索 -> amount=None，missing_fields 加 "amount"（交给页面人工确认）
    类别：CATEGORY_KEYWORDS 扫关键词，没中就 DEFAULT_CATEGORY
    时间：昨天/前天/今天
    置信度：金额和类别都抓到 = 0.9，否则 0.5
    """
    # ① 抓金额：先屏蔽非金额数字，再从候选里选实际支付
    amount = _extract_amount(text)

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
