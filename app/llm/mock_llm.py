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
    "工资5000"               -> 金额 5000，方向收入

已知做不到（mock 的边界，遇到就返回 None 或低置信度，让页面人工确认）：
- 中文数字/模糊数：三十、两百、一万五
- 元角分混合：25元5角、1块5
- 单价×人数/份数写在后面：25元/人，2人；25元一份，买2份
- 只给原价+折扣、不给实付：100元打8折
- 一条消息多笔：午饭25，打车30
- 万/千简写：3万5（当前只认 3万，不认后面的 5 千）
- 绝对日期：11月20号 会写入 occurred_at（年份取今年）；2月30号等非法日期回退今天
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from app.constants import DEFAULT_CATEGORY, DIRECTION_EXPENSE, DIRECTION_INCOME

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
    "消费", "充值", "充", "退回", "券后", "优惠后", "折后", "现价", "到手价", "买", "交", "缴",
)
NEGATIVE_CUES = ("原价", "优惠", "券", "小费", "押金", "定金")
NEGATIVE_EDGE_CUES = ("满", "减", "省")

# 收入方向：词必须紧贴选中的金额，避免“退款失败，午饭25”被误判成收入
INCOME_KEYWORDS: tuple[str, ...] = (
    "工资", "薪水", "薪资", "收入", "进账", "报销", "退款", "退回",
    "奖金", "年终奖", "加班费", "补贴", "补助", "利息", "分红", "稿费",
    "兼职", "外快", "返现", "中奖", "压岁钱",
    "收到红包", "收红包", "抢红包",
)
# 收入词紧贴金额的最大间隔（字符）
DIRECTION_WINDOW = 4
# 收入词后面出现这些词，说明不是在说一笔收入
INCOME_NEGATION_AFTER: tuple[str, ...] = (
    "失败", "未", "没", "没有", "不", "别", "流程", "说明", "明细",
    "记录", "计划", "申请", "待", "预计", "应该", "吗", "?", "？",
)
INCOME_NEGATION_BEFORE: tuple[str, ...] = ("没", "未", "不", "没有", "别")
# 这些支出词紧贴金额时，方向优先判支出（如“收到红包200，买咖啡25”）
EXPENSE_NEAR_CUES: tuple[str, ...] = (
    "发红包", "给红包", "送红包", "支出", "花了", "花", "付了", "付款",
    "支付", "消费", "买", "交", "缴", "转给",
)
EXPENSE_WINDOW = 3
# 券面额：金额后紧跟"元券/元优惠券"（如"3元券"），是券的面值不是消费金额
COUPON_FACE_RE = re.compile(r"(?:优惠)?券")
# 中文绝对日期："11月20号/11月20日"（用于 occurred_at，年份取今年）
CN_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})月(\d{1,2})[号日](?!\d)")


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


def _pick_amount(text: str) -> tuple[float | None, int, int]:
    """从一句话里选一个金额；返回 (金额, 起始位置, 结束位置)。

"主价格 + 优惠"会取主价格（奶茶15，用券减3 -> 15），不整句放弃；
    坏金额仍返回 (None, -1, -1)：原价50 / 优惠20 / 满100 / 减20 / 3元券（券面额）。
    多个等分候选分不清哪个是主金额时也返回 (None, -1, -1)。
    """
    amount_text = _mask_non_amounts(text)
    candidates: list[dict] = []
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
        # negative 拆成"金额前/金额后"：原价50/满100减20 的修饰词在金额前，是坏金额；
        # "奶茶15，用券减3"的"券"在 15 后面，15 本身仍是主价格，不能整句放弃
        neg_before = any(cue in before for cue in NEGATIVE_CUES) or any(
            before.endswith(cue) for cue in NEGATIVE_EDGE_CUES
        )
        neg_after = any(cue in after for cue in NEGATIVE_CUES)
        # 券面额："3元券/3元优惠券"，金额本身是券的面值，不是消费
        after_full = amount_text[m.end():m.end() + 8]
        coupon_face = bool(has_unit and COUPON_FACE_RE.match(after_full))
        score = (3 if has_unit else 0) + (4 if actual else 0) - (
            2 if (neg_before or neg_after) else 0
        )
        candidates.append({
            "value": value, "score": score, "actual": actual,
            "neg_before": neg_before, "coupon_face": coupon_face,
            "start": m.start(), "end": m.end(),
        })

    if not candidates:
        return None, -1, -1
    # 先排除"坏金额"：修饰词在金额前（原价50/优惠20/满100/减20）或券面额（3元券）
    # 有"实付/券后"等线索时，金额前的负面词失效（券后实付25 -> 25，不是券面额）
    usable = [
        c for c in candidates
        if (c["actual"] or not c["neg_before"]) and not c["coupon_face"]
    ]
    if not usable:
        return None, -1, -1
    best_score = max(c["score"] for c in usable)
    best = [c for c in usable if c["score"] == best_score]
    # 同分且金额不同：分不清哪个是主金额，宁可不猜（多笔账交给页面人工确认）
    if len(best) > 1 and len({c["value"] for c in best}) > 1:
        return None, -1, -1
    chosen = best[0]
    return chosen["value"], chosen["start"], chosen["end"]


def _extract_amount(text: str) -> float | None:
    """兼容旧调用：只返回金额。"""
    return _pick_amount(text)[0]


def _span_gap(start_a: int, end_a: int, start_b: int, end_b: int) -> int:
    """两个区间之间隔了几个字符；重叠返回 0。"""
    if end_a <= start_b:
        return start_b - end_a
    if end_b <= start_a:
        return start_a - end_b
    return 0


def _income_hit_is_valid(text: str, start: int, keyword: str) -> bool:
    """收入词前后不能是否定/流程类说法，例如“退款失败”“没发工资”。"""
    end = start + len(keyword)
    before = text[max(0, start - 2):start]
    after = text[end:end + 3]
    return not any(w in before for w in INCOME_NEGATION_BEFORE) and not any(
        w in after for w in INCOME_NEGATION_AFTER
    )


def _iter_income_hits(text: str):
    """遍历所有有效的收入词位置。"""
    for keyword in INCOME_KEYWORDS:
        idx = text.find(keyword)
        while idx != -1:
            if _income_hit_is_valid(text, idx, keyword):
                yield idx, idx + len(keyword)
            idx = text.find(keyword, idx + 1)


def _has_income_keyword(text: str) -> bool:
    """整句里有没有有效的收入词（金额没选出来时的兜底）。"""
    return next(_iter_income_hits(text), None) is not None


def _has_income_near_amount(text: str, amount_start: int, amount_end: int) -> bool:
    """收入词必须紧贴选中的金额，不能只看全句。"""
    return any(
        _span_gap(start, end, amount_start, amount_end) <= DIRECTION_WINDOW
        for start, end in _iter_income_hits(text)
    )


def _has_expense_near_amount(text: str, amount_start: int, amount_end: int) -> bool:
    """支出词紧贴金额时优先判支出，处理“收到红包200，买咖啡25”。"""
    for cue in EXPENSE_NEAR_CUES:
        idx = text.find(cue)
        while idx != -1:
            if _span_gap(idx, idx + len(cue), amount_start, amount_end) <= EXPENSE_WINDOW:
                return True
            idx = text.find(cue, idx + 1)
    return False


def _detect_direction(text: str, amount: float | None, amount_start: int, amount_end: int) -> tuple[str, bool]:
    """判断收支方向；返回 (direction, 是否明确命中收入词)。

    原则：方向跟着“选中的金额”走，不跟全句关键词走。
    - 收入词必须紧贴选中的金额（±4 字），否则不认
    - 支出词紧贴金额（±3 字）时优先判支出
    - 没命中收入词就按默认支出
    """
    direction_text = _mask_non_amounts(text)
    if amount is not None and amount_start >= 0:
        income_near = _has_income_near_amount(direction_text, amount_start, amount_end)
        expense_near = _has_expense_near_amount(direction_text, amount_start, amount_end)
        if income_near and not expense_near:
            return DIRECTION_INCOME, True
        return DIRECTION_EXPENSE, False
    # 金额没选出来（多笔/歧义）时，只能看全句有没有明确收入词
    if _has_income_keyword(direction_text):
        return DIRECTION_INCOME, True
    return DIRECTION_EXPENSE, False


def parse_record(text: str) -> dict:
    """离线版 parse_record。返回结构和 B 的正式版完全一致。

    金额策略：
        1. 先屏蔽日期、时间、订单/电话/房间号、楼层/线路/数量等非金额数字
        2. 从剩余候选里选“实际支付”：只有一个候选就用；多个候选优先“实付/花了/充值”等线索
        3. "主价格 + 优惠"取主价格（奶茶15，用券减3 -> 15）；原价/满减/券面额排除掉
        4. 多个等分候选分不清主金额 -> amount=None，missing_fields 加 "amount"（交给页面人工确认）
    方向：
        工资/收入/报销/退款/奖金/利息/分红/稿费/兼职/外快/返现/中奖/补贴/加班费/压岁钱/收到红包
        必须紧贴选中的金额才判 income；其余默认 expense；支出词紧贴金额时优先 expense
    类别：CATEGORY_KEYWORDS 扫关键词，没中就 DEFAULT_CATEGORY
    时间：绝对日期（11月20号，年份取今年）> 前天 > 昨天 > 今天
    置信度：金额 +（类别或收入方向）命中 = 0.9，否则 0.5
    """
    # ① 抓金额：先屏蔽非金额数字，再从候选里选实际支付；同时保留位置供方向判断
    amount, amount_start, amount_end = _pick_amount(text)

    # ② 定方向：收入词必须紧贴选中的金额，避免“退款失败，午饭25”被误判
    direction, direction_hit = _detect_direction(text, amount, amount_start, amount_end)

    # ③ 定类别：扫关键词表
    category = DEFAULT_CATEGORY
    hit_keyword = False
    for cat, words in CATEGORY_KEYWORDS.items():
        if any(w in text for w in words):
            category = cat
            hit_keyword = True
            break

    # ④ 定时间：绝对日期（11月20号）> 前天 > 昨天 > 今天
    now = datetime.now()
    m_date = CN_DATE_RE.search(text)
    if m_date:
        try:
            day = now.replace(month=int(m_date.group(1)), day=int(m_date.group(2)))
        except ValueError:
            day = now  # 非法日期（如2月30号）回退今天
    elif "前天" in text:
        day = now - timedelta(days=2)
    elif "昨天" in text:
        day = now - timedelta(days=1)
    else:
        day = now

    # ⑤ 缺金额就记下来
    missing = []
    if amount is None:
        missing.append("amount")

    # ⑥ 置信度：金额 +（类别或收入方向）命中
    confidence = 0.9 if (amount is not None and (hit_keyword or direction_hit)) else 0.5

    # 组装 9 个字段返回
    return {
        "amount": amount,
        "direction": direction,
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
    best_cat = DEFAULT_CATEGORY
    best_hits = 0
    for cat, words in CATEGORY_KEYWORDS.items():
        hits = sum(1 for w in words if w in text)
        if hits > best_hits:
            best_hits = hits
            best_cat = cat
    if best_hits == 0:
        return DEFAULT_CATEGORY, 0.3
    confidence = 0.9 if best_hits >= 2 else 0.7
    return best_cat, confidence


def parse_query(text: str) -> dict:
    """离线版查账解析（第 7-8 天）。

    原则：日期由代码精确算，不靠模型；认不出的问法明确报错，不瞎编。

    返回 {"metric": "sum"|"rank"|"count"|"compare",
          "time_start": "YYYY-MM-DD", "time_end": "YYYY-MM-DD",
          "category": "餐饮"|None, "direction": "expense"|"income"}

    - metric 判断按顺序特判（"哪类花得最多"里有"花"，所以 rank 必须在 sum 前）：
      compare（比/对比/比较/多花了/少花了）> rank（哪类/最多/排行）> count（几笔/笔数）> sum（多少/花了）
      一个都不沾 -> ValueError，页面提示"没听懂"
    - 时间：上月、本月/这个月（默认）、今年、本周、上周、最近N天、今天、昨天
      月末用"下月 1 号减 1 天"算，保证 10 月是 31 天
    - compare 的区间：含"上月/上个月"从上月 1 号到今天，否则本月 1 号到今天
      （覆盖对比的两个月，answer_query 再按月切）
    - 类别：CATEGORY_KEYWORDS 扫，多类命中取第一个（"吃饭和打车"只认"餐饮"）
    - 方向：INCOME_KEYWORDS 扫全句，命中 income，否则 expense

    已知边界：只说类别词不带问法（如"吃饭"）会抛 ValueError；
    绝对日期（"11月20号花了多少"）不支持，按默认本月。
    """
    now = datetime.now()
    today = now.date()

    # ① metric：compare > rank > count > sum，顺序不能乱
    if any(w in text for w in ("比", "对比", "比较", "多花了", "少花了", "多还是少")):
        metric = "compare"
    elif any(w in text for w in ("哪类", "哪一类", "最多", "排行", "大头", "占比", "top")):
        metric = "rank"
    elif any(w in text for w in ("几笔", "多少笔", "笔数", "几次", "记了")):
        metric = "count"
    elif any(w in text for w in ("多少", "花了", "支出", "消费", "用了", "买了")):
        metric = "sum"
    else:
        raise ValueError("没听懂这个问题，试试『上个月吃饭花了多少』")

    # ② 时间区间：代码精确算（月末用"下月 1 号减 1 天"，不会少一天）
    if "上个月" in text or "上月" in text:
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        if metric == "compare":
            start, end = last_prev.replace(day=1), today
        else:
            start, end = last_prev.replace(day=1), last_prev
    elif "今年" in text:
        start, end = today.replace(month=1, day=1), today
    elif "本周" in text or "这周" in text:
        start = today - timedelta(days=today.weekday())
        end = today
    elif "上周" in text:
        this_monday = today - timedelta(days=today.weekday())
        start = this_monday - timedelta(days=7)
        end = this_monday - timedelta(days=1)
    elif (m := re.search(r"最近\s*(\d+)\s*天|近\s*(\d+)\s*天", text)) is not None:
        n = int(m.group(1) or m.group(2))
        start = today - timedelta(days=n)
        end = today
    elif "今天" in text:
        start = end = today
    elif "昨天" in text:
        start = end = today - timedelta(days=1)
    else:
        # 没提时间：默认本月（1 号到今天）
        start, end = today.replace(day=1), today

    # ③ 类别：扫关键词表，多类命中取第一个（与 parse_record 同一张表）
    category = None
    for cat, words in CATEGORY_KEYWORDS.items():
        if any(w in text for w in words):
            category = cat
            break

    # ④ 方向：收入词命中 income，否则 expense（查账默认问"花了多少"）
    direction = (
        DIRECTION_INCOME if any(w in text for w in INCOME_KEYWORDS)
        else DIRECTION_EXPENSE
    )

    return {
        "metric": metric,
        "time_start": start.strftime("%Y-%m-%d"),
        "time_end": end.strftime("%Y-%m-%d"),
        "category": category,
        "direction": direction,
    }