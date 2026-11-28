"""记账页（Owner: C｜第 3-4 天｜数据对接：B）

页面流程（这也是答辩会被问的那道题，要能讲清楚）：
    1. 用户在输入框打"午饭 25，和同事 AA"
    2. 点"解析" -> 调 B 的 parse_record(text)
    3. 屏幕上出现一张确认卡片，显示 金额 / 类别 / 时间 / 商户
    4. 用户在卡片里可以改任何一项
    5. 点"确认记账" -> 调 A 的 add_transaction(record)
    6. 提示"已记上"，清空输入框
    7. 如果 B 返回的 missing_fields 非空 -> 卡片上显示追问，不让直接确认

分工边界：
    - 卡片长什么样、按钮放哪、布局怎么排 = 页面负责人（本文件）
    - 卡片里每个字段显示什么、缺字段时提示什么 = B（返回的 missing_fields 决定提示）

⚠️ 第 3-4 天的过渡态（先看完这段再看代码）：
    B 的 parse_record() 和 A 的 add_transaction() 现在都还是 NotImplementedError，
    所以本文件自带一条"演示兜底"，接口一实现就自动切到真函数：

        解析：B 的 parse_record 可用  -> 用它
              B 还没写完 / 报错       -> _demo_parse()，正则 + 关键词，只够演示
        入库：A 的 add_transaction 可用 -> 用它，返回真实 id
              A 还没写完 / 报错       -> 先放在本次会话（session_state）里，页面明说

    切换点只有 _parse_text() 和 _save_record() 两个函数。B/A 写完以后，
    这个页面**一行都不用改**——这就是"先写死、后对接"能省事的原因。

为什么不用 st.dialog 弹窗：
    st.dialog 里改控件会触发整个页面的 rerun，零基础阶段很容易和
    session_state 打架。改用 `st.container(border=True)` 在输入框正下方
    "长出一张卡片"，视觉上一样是"弹出来"，状态好理解、好调试。
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import streamlit as st

from app.constants import (
    CATEGORIES,
    DEFAULT_CATEGORY,
    DIRECTION_EXPENSE,
    DIRECTION_INCOME,
    DIRECTIONS,
    SOURCE_RECEIPT,
    SOURCE_TEXT,
)
from app.db.conn import DATETIME_FMT

# ---------- 和 A / B 的两个交界点（都做了"没写完也能跑"的兜底）----------
try:  # B 的正式解析
    from app.llm.parser import parse_record as _parse_record_from_b
except Exception:  # pragma: no cover - 只在 B 的模块还不能 import 时走到
    _parse_record_from_b = None

try:  # A 的入库
    from app.services.ledger import add_transaction as _add_transaction_from_a
except Exception:  # pragma: no cover
    _add_transaction_from_a = None

try:  # C 的小票识别（第 5-6 天接通；没接通时页面只显示错误，不影响文字记账）
    from app.ocr.receipt import LOW_CONFIDENCE as _OCR_LOW_CONFIDENCE
    from app.ocr.receipt import extract_receipt as _extract_receipt_from_c
except Exception:  # pragma: no cover
    _extract_receipt_from_c = None
    _OCR_LOW_CONFIDENCE = 0.6


# ============================================================
# 一、演示兜底用的"土办法解析"（B 的 parse_record 好了就可以整段删掉）
# ============================================================

_DEMO_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("餐饮", ("饭", "早餐", "午餐", "晚餐", "咖啡", "奶茶", "外卖", "食堂",
             "火锅", "烧烤", "面", "水果", "吃")),
    ("交通", ("打车", "出租", "地铁", "公交", "高铁", "火车", "机票", "加油",
             "停车", "单车", "滴滴")),
    ("购物", ("买", "淘宝", "京东", "拼多多", "超市", "衣服", "鞋", "耳机")),
    ("娱乐", ("电影", "游戏", "KTV", "唱歌", "会员", "演唱会", "剧本杀")),
    ("居住", ("房租", "水电", "物业", "宽带", "燃气")),
    ("医疗", ("药", "医院", "挂号", "体检", "牙")),
    ("教育", ("书", "课程", "学费", "考试", "培训")),
    ("通讯", ("话费", "流量", "充值")),
    ("人情", ("红包", "份子", "礼物", "随礼")),
)
_DEMO_INCOME_KEYWORDS = ("工资", "奖金", "收到", "退款", "报销", "收入")

# 金额：先找带"元/块"的（避免把"3号线"认成 3 元），找不到再找裸数字
_AMOUNT_STRICT_RE = re.compile(r"(?:￥|¥)?\s*(\d+(?:\.\d{1,2})?)\s*(?:元|块)")
_AMOUNT_LOOSE_RE = re.compile(r"(\d+(?:\.\d{1,2})?)")
_MERCHANT_RE = re.compile(r"(?:在|去|到)([\u4e00-\u9fa5A-Za-z0-9]{2,10})")

# 模糊时间：只说"中午/晚上"时，按用餐时段取整点（和 B 的 prompt 规则一致）
_TIME_OF_DAY: tuple[tuple[str, int], ...] = (
    ("早饭", 8), ("早餐", 8), ("早上", 8),
    ("午饭", 12), ("午餐", 12), ("中午", 12), ("下午", 15),
    ("晚饭", 19), ("晚餐", 19), ("晚上", 19), ("夜宵", 22),
)


def _demo_parse(text: str) -> dict:
    """离线版解析，只覆盖"能演示"的几种说法。

    返回结构和 B 的 parse_record 完全一致，少一个字段都不行（页面只认这一套）。
    做不到的情况不硬猜：金额抓不到就返回 None + missing_fields=["amount"]。
    """
    body = (text or "").strip()

    m = _AMOUNT_STRICT_RE.search(body) or _AMOUNT_LOOSE_RE.search(body)
    amount = float(m.group(1)) if m else None

    hits = [(sum(1 for kw in words if kw in body), cat)
            for cat, words in _DEMO_CATEGORY_KEYWORDS]
    hits = [(n, cat) for n, cat in hits if n > 0]
    category = max(hits)[1] if hits else DEFAULT_CATEGORY

    direction = (
        DIRECTION_INCOME
        if any(kw in body for kw in _DEMO_INCOME_KEYWORDS)
        else DIRECTION_EXPENSE
    )

    day = date.today()
    if "前天" in body:
        day -= timedelta(days=2)
    elif "昨天" in body:
        day -= timedelta(days=1)

    hour = 12
    for word, h in _TIME_OF_DAY:
        if word in body:
            hour = h
            break
    occurred_at = f"{day.isoformat()} {hour:02d}:00:00"

    merchant = None
    mm = _MERCHANT_RE.search(body)
    if mm:
        merchant = mm.group(1)

    if amount is None:
        confidence, missing = 0.3, ["amount"]
    elif hits:
        confidence, missing = 0.9, []
    else:
        confidence, missing = 0.5, []

    return {
        "amount": amount,
        "direction": direction,
        "category": category,
        "subcategory": None,
        "merchant": merchant,
        "note": None,
        "occurred_at": occurred_at,
        "confidence": confidence,
        "missing_fields": missing,
    }


# ============================================================
# 二、把 B 返回的东西"消毒"成页面能用的结构
# ============================================================

def _norm_amount(value) -> float | None:
    """把 25 / "25" / "25元" / None 统一成 float 或 None。"""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip().replace("元", "").replace("块", "")
        if not value:
            return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return round(num, 2) if num > 0 else None


def _norm_datetime(value) -> str:
    """把模型可能给出的各种时间写法统一成 'YYYY-MM-DD HH:MM:SS'。"""
    if isinstance(value, datetime):
        return value.strftime(DATETIME_FMT)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day).strftime(DATETIME_FMT)
    if isinstance(value, str) and value.strip():
        raw = value.strip()
        for fmt in (DATETIME_FMT, "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M",
                    "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
            try:
                return datetime.strptime(raw, fmt).strftime(DATETIME_FMT)
            except ValueError:
                continue
    # 解析不出来就按"现在"算，总比让页面崩掉强
    return datetime.now().strftime(DATETIME_FMT)


def _normalize(raw: dict, text: str) -> dict:
    """字段补全 + 类型校验。**页面只认这一个结构**。"""
    raw = raw if isinstance(raw, dict) else {}

    amount = _norm_amount(raw.get("amount"))
    category = raw.get("category")
    if category not in CATEGORIES:
        category = DEFAULT_CATEGORY
    direction = raw.get("direction")
    if direction not in DIRECTIONS:
        direction = DIRECTION_EXPENSE

    missing = [str(x) for x in (raw.get("missing_fields") or []) if str(x)]
    if amount is None and "amount" not in missing:
        missing.append("amount")
    if amount is not None and "amount" in missing:
        missing.remove("amount")

    confidence = raw.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = None

    return {
        "amount": amount,
        "direction": direction,
        "category": category,
        "subcategory": (raw.get("subcategory") or None),
        "merchant": (raw.get("merchant") or None),
        "note": (raw.get("note") or None),
        "occurred_at": _norm_datetime(raw.get("occurred_at")),
        "confidence": confidence,
        "missing_fields": missing,
        "raw_input": text,
        "source": SOURCE_TEXT,
    }


# ============================================================
# 三、两个交界点的"能跑就跑真的，跑不了走演示"
# ============================================================

def _parse_text(text: str) -> tuple[dict, str]:
    """一句话 -> (标准 record, 给用户看的说明)。

    说明为空 = 走的 B 的正式解析；非空 = 走了演示兜底，原因写在里面。
    """
    if _parse_record_from_b is not None:
        try:
            raw = _parse_record_from_b(text)
            return _normalize(raw, text), ""
        except NotImplementedError:
            note = "B 的 parse_record() 还没接通，当前用页面内置的规则解析（够演示，不追求准确）。"
        except Exception as exc:  # 模型超时、JSON 坏、Key 失效……都不能让页面崩
            note = (f"parse_record 报错（{type(exc).__name__}: {exc}），"
                    "已退回页面内置的规则解析。")
    else:
        note = "还没找到 B 的 parse_record()，当前用页面内置的规则解析。"

    return _normalize(_demo_parse(text), text), note


def _save_record(record: dict) -> tuple[int | None, str]:
    """record -> (数据库 id, 说明)。id 为 None 表示没入库（演示模式）。

    ⚠️ 传出去的 record 不许带 "_id" 这类页面内部字段，入库函数只认契约里的字段。
    """
    payload = {k: v for k, v in record.items() if not k.startswith("_")}

    if _add_transaction_from_a is None:
        return None, "还没找到 A 的 add_transaction()，这笔账只放在本次会话里，刷新就没了。"

    try:
        return int(_add_transaction_from_a(payload)), ""
    except NotImplementedError:
        return None, "A 的 add_transaction() 还没接通，这笔账只放在本次会话里，刷新就没了。"
    except Exception as exc:
        message = str(exc)
        if "no such table" in message:
            return None, (
                "数据库还没初始化：先在项目根目录跑 "
                "`python -c \"from app.db.conn import init_db; init_db()\"`，再点一次确认。"
            )
        return None, f"入库失败（{type(exc).__name__}: {exc}），这笔账只放在本次会话里。"


def _needs_review(record: dict) -> bool:
    """要不要强制人工逐项核对。

    两条判据（和 app/ocr/receipt.needs_manual_review 保持一致的口径）：
    1. 置信度低于阈值（模型自己说没把握）
    2. missing_fields 非空（少了字段，等于没认全）

    为什么页面自己再判一次、不直接调 needs_manual_review：
    文字记账那条路没有 OCR 模块也能用，不能因为一个可选依赖把页面搞挂。
    """
    if record.get("missing_fields"):
        return True
    confidence = record.get("confidence")
    return isinstance(confidence, (int, float)) and confidence < _OCR_LOW_CONFIDENCE


def _record_from_ocr(result: dict) -> dict:
    """把 extract_receipt 的结果变成页面草稿。

    小票识别和一句话解析能共用同一张确认卡片，靠的就是这里把结构对齐：
    extract_receipt 返回的字段和 parse_record 完全一样，只多一个 raw_text。
    """
    record = dict(result)
    record["source"] = SOURCE_RECEIPT
    # ledger 的 raw_input 约定是"用户原话或 OCR 原文"。
    # 不存的话，事后想查"当时图上到底写了什么"就只剩 raw_text 在页面里，刷新就没了。
    record["raw_input"] = (str(result.get("raw_text") or "")[:1000] or None)
    confidence = result.get("confidence")
    if isinstance(confidence, (int, float)):
        record["_note"] = f"来源：小票识别（置信度 {confidence:.0%}）"
    else:
        record["_note"] = "来源：小票识别"
    record["_source"] = "vision"
    return record


# ============================================================
# 四、session_state 管理（Streamlit 的坑基本都在这里）
# ============================================================

# 卡片的控件 key：rec_<draft_id>_<字段名>。
# 用 draft_id 区分"这一次解析"，换一句话就要换一套 key，否则控件还留着上次的值。
_CARD_FIELDS = ("amount", "direction", "category", "date", "time",
                "merchant", "note", "sub", "save", "cancel", "ack")

_EXAMPLES = (
    "午饭 25，和同事 AA",
    "昨天打车 32",
    "星巴克花了三十多",
)

_DIRECTION_LABELS = {DIRECTION_EXPENSE: "支出", DIRECTION_INCOME: "收入"}

# missing_fields 的中文追问（B 只说字段名，怎么说人话是页面的事）
_MISSING_HINTS = {
    "amount": "没听清金额，请在「金额」里补上",
    "category": "类别没定下来，请选一个",
    "occurred_at": "时间没说清，先按今天算，可以改",
    "merchant": "商户没认出来，留空也行",
    "direction": "没分清是收入还是支出，默认按支出算",
}
_FIELD_LABELS = {
    "amount": "金额",
    "category": "类别",
    "occurred_at": "时间",
    "merchant": "商户",
    "direction": "收支",
}


def _seed_widgets(record: dict) -> None:
    """新建草稿后，把值塞进 session_state。

    必须在控件**创建之前**赋值，这是 Streamlit 的硬性要求（否则报
    "cannot be modified after the widget is instantiated"）。
    """
    kid = record["_id"]
    # 顺手清掉上一张卡片留下的 key（它们在本轮还没被创建，删是安全的）
    for key in list(st.session_state.keys()):
        if re.match(r"^rec_\d+_", key) and not key.startswith(f"rec_{kid}_"):
            del st.session_state[key]

    dt = datetime.strptime(record["occurred_at"], DATETIME_FMT)
    st.session_state[f"rec_{kid}_amount"] = float(record["amount"] or 0.0)
    st.session_state[f"rec_{kid}_direction"] = record["direction"]
    st.session_state[f"rec_{kid}_category"] = record["category"]
    st.session_state[f"rec_{kid}_date"] = dt.date()
    st.session_state[f"rec_{kid}_time"] = dt.time()
    st.session_state[f"rec_{kid}_merchant"] = record.get("merchant") or ""
    st.session_state[f"rec_{kid}_note"] = record.get("note") or ""
    st.session_state[f"rec_{kid}_sub"] = record.get("subcategory") or ""


def _drop_draft_state() -> None:
    """丢掉当前草稿和它的控件 key。只能在控件创建之前调用。"""
    draft = st.session_state.pop("rec_draft", None)
    if not draft:
        return
    kid = draft.get("_id")
    for name in _CARD_FIELDS:
        st.session_state.pop(f"rec_{kid}_{name}", None)


def _apply_pending() -> None:
    """把"上一轮点按钮许下的诺言"兑现。

    为什么要绕这一层：按钮点击时输入框/卡片控件已经创建过了，
    这时改它们的 session_state 会直接抛异常。所以按钮只写一个 pending，
    下一轮一开始（任何控件都还没创建）再统一执行。
    """
    pend = st.session_state.pop("rec_pending", None)
    if not pend:
        return
    if pend.get("drop_draft"):
        _drop_draft_state()
    if "text" in pend:
        st.session_state["rec_text"] = pend["text"]
    if pend.get("flash"):
        st.session_state["rec_flash"] = pend["flash"]
    if pend.get("warn"):
        st.session_state["rec_warn"] = pend["warn"]


def _flash_text(record: dict, tx_id: int | None) -> str:
    """记成功后顶部那行绿字。"""
    head = f"已记上：{record['amount']:.2f} 元 · {record['category']} · {record['occurred_at'][:16]}"
    if tx_id is None:
        return head + "（演示：没进数据库）"
    return head + f"（编号 #{tx_id}）"


# ============================================================
# 五、确认卡片
# ============================================================

def render_confirm_card(record: dict) -> dict | None:
    """把 B 返回的 record 渲染成可编辑的确认卡片，返回用户改完后的 record。

    返回值：
        dict  -> 用户点了「确认记账」，这是改完的数据（由 render() 负责入库）
        None  -> 什么都没发生（或用户点了取消，取消在这里就地处理）

    这个函数是页面和 B 的交界：
    - 页面负责控件和布局
    - B 负责 record 里有哪些字段、missing_fields 里有什么
    """
    kid = record["_id"]

    def key(name: str) -> str:
        return f"rec_{kid}_{name}"

    with st.container(border=True):
        head_left, head_right = st.columns([3, 1], vertical_alignment="center")
        head_left.markdown("#### 确认一下这笔账，哪项不对直接改")

        confidence = record.get("confidence")
        shown = f"{confidence:.0%}" if isinstance(confidence, (int, float)) else "未知"
        head_right.caption(f"AI 把握：{shown}")

        # 来源说明：让人一眼看出这一步到底有没有调模型
        src = record.get("_source")
        if src == "fallback":
            st.caption(f"⚠️ 当前为离线兜底解析（{record.get('_note') or '规则匹配'}）· 把握 {shown}")
        elif src == "vision":
            st.caption(f"✅ 已用小票识别（视觉模型）· 把握 {shown}")
        elif src == "llm":
            st.caption(f"✅ 已用大模型解析 · 把握 {shown}")
        else:
            st.caption(f"解析方式未标记 · 把握 {shown}")

        missing = list(record.get("missing_fields") or [])
        if missing:
            hints = [_MISSING_HINTS.get(f, f"缺少「{_FIELD_LABELS.get(f, f)}」") for f in missing]
            st.warning("AI 没完全听清：" + "；".join(hints) + "。补上才能记账。")
            if "amount" in missing:
                st.caption(
                    "这句话里没有确切金额，模型**没有猜**（避免记进一个你没确认过的数字）——"
                    "请在上面的「金额」里补一个数。"
                )

        raw_text = record.get("raw_text")
        if raw_text:
            with st.expander("查看识别到的原文（核对用）"):
                st.text(str(raw_text)[:800])

        row1 = st.columns(3)
        amount = row1[0].number_input(
            "金额（元）", min_value=0.0, step=1.0, format="%.2f", key=key("amount")
        )
        direction = row1[1].radio(
            "收支",
            options=[DIRECTION_EXPENSE, DIRECTION_INCOME],
            format_func=lambda d: _DIRECTION_LABELS.get(d, d),
            horizontal=True,
            key=key("direction"),
        )
        category = row1[2].selectbox("类别", options=list(CATEGORIES), key=key("category"))

        row2 = st.columns(3)
        day = row2[0].date_input("日期", key=key("date"))
        clock = row2[1].time_input("时间", step=60, key=key("time"))
        merchant = row2[2].text_input("商户（可空）", key=key("merchant"))

        with st.expander("备注 / 小类（可空）"):
            note = st.text_input("备注", key=key("note"))
            subcategory = st.text_input("小类", key=key("sub"))

        if amount <= 0:
            st.caption("金额还空着，填上才能记；不想记了就点「取消」。")

        # AI 没把握时，不能让人闭着眼点确认（第 8 天的验收项）。
        # 判据两条：置信度低于阈值，或者 missing_fields 非空。
        needs_review = _needs_review(record)
        acknowledged = True
        if needs_review:
            confidence = record.get("confidence")
            shown = f"{confidence:.0%}" if isinstance(confidence, (int, float)) else "未知"
            st.error(f"AI 对这次识别没把握（置信度 {shown}），必须逐项核对后才能记账。")
            acknowledged = st.checkbox(
                "我已逐项核对金额、类别、时间、商户", key=key("ack")
            )

        btn_save_col, btn_cancel_col, _ = st.columns([1, 1, 3])
        save = btn_save_col.button(
            "✅ 确认记账", type="primary", width="stretch",
            disabled=(amount <= 0) or (needs_review and not acknowledged),
            key=key("save"),
        )
        cancel = btn_cancel_col.button("取消", width="stretch", key=key("cancel"))

        if cancel:
            st.session_state["rec_pending"] = {
                "drop_draft": True,
                "text": "",
                "flash": None,
                "warn": None,
            }
            st.rerun()

        if save:
            occurred_at = f"{day.isoformat()} {clock.strftime('%H:%M:%S')}"
            return _compose_record(
                record,
                amount=amount,
                direction=direction,
                category=category,
                occurred_at=occurred_at,
                merchant=merchant,
                note=note,
                subcategory=subcategory,
            )

    return None


# ============================================================
# 六、整页
# ============================================================

def _compose_record(record: dict, *, amount: float, direction: str, category: str,
                    occurred_at: str, merchant: str | None, note: str | None,
                    subcategory: str | None) -> dict:
    """把卡片上的值组装成入库用的 record。

    ⚠️ source 必须从草稿继承：小票识别传的是 receipt，写死成 text 的话，
    数据库里就分不出"这张账是拍照来的还是打字来的"——答辩要统计三种录入方式会直接翻车。
    """
    return {
        "amount": round(float(amount), 2),
        "direction": direction,
        "category": category,
        "subcategory": (subcategory or "").strip() or None,
        "merchant": (merchant or "").strip() or None,
        "note": (note or "").strip() or None,
        "occurred_at": occurred_at,
        "confidence": record.get("confidence"),
        # missing_fields 是确认卡片（草稿）的展示字段，不是入库契约——
        # add_transaction 对契约外字段直接报错，这里不能把它带出去。
        "raw_input": record.get("raw_input"),
        "source": record.get("source") or SOURCE_TEXT,
    }


def render() -> None:
    """渲染记账页。"""
    _apply_pending()

    st.subheader("一句话记账")
    st.caption("打一句人话，系统把金额 / 类别 / 时间 / 商户填好，你核对后再入库。")

    if st.session_state.get("rec_flash"):
        st.success(st.session_state["rec_flash"])
    if st.session_state.get("rec_warn"):
        st.info(st.session_state["rec_warn"])

    col_text, col_btn = st.columns([5, 1], vertical_alignment="bottom")
    with col_text:
        st.text_input(
            "你说一句话",
            key="rec_text",
            label_visibility="collapsed",
            placeholder="例：午饭 25，和同事 AA",
        )
    with col_btn:
        parse_clicked = st.button(
            "解析", type="primary", width="stretch", key="rec_parse"
        )

    # 三个示例句子：评审现场不用手打，点一下就填（演示友好）
    picked = None
    for col, example in zip(st.columns(3), _EXAMPLES):
        if col.button(example, width="stretch", key=f"rec_ex_{example}"):
            picked = example
    if picked is not None:
        st.session_state["rec_pending"] = {"text": picked}
        st.rerun()

    if parse_clicked:
        text = (st.session_state.get("rec_text") or "").strip()
        if not text:
            st.warning("先打一句话，比如『午饭 25，和同事 AA』。")
        else:
            with st.spinner("正在解析这句话…（走真模型约 3-7 秒，离线兜底会很快）"):
                record, note = _parse_text(text)
            st.session_state["rec_parse_state"] = (
                "页面内置规则（B 的 parse_record 未接通）" if note else "B 的 parse_record"
            )
            record["_id"] = int(st.session_state.get("rec_draft_seq", 0)) + 1
            record["_note"] = note
            # 标记这一笔是"真模型解析"还是"离线兜底"，卡片上要给用户看
            record["_source"] = "fallback" if note else "llm"
            st.session_state["rec_draft_seq"] = record["_id"]
            st.session_state["rec_draft"] = record
            st.session_state["rec_flash"] = None
            st.session_state["rec_warn"] = None
            _seed_widgets(record)

    # ---------- 拍小票：和"一句话记账"共用同一张确认卡片 ----------
    # C 的 OCR 接通了就直接用；没接通（或没 Key）时这里只显示错误，不影响文字记账。
    with st.expander("📷 或者：拍张小票 / 传张支付截图", expanded=False):
        uploaded = st.file_uploader(
            "选择图片",
            type=["jpg", "jpeg", "png", "webp"],
            key="rec_upload",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            st.caption(f"{uploaded.name} · {uploaded.size / 1024:.0f} KB")
        ocr_clicked = st.button(
            "识别这张图",
            key="rec_ocr",
            width="stretch",
            disabled=uploaded is None,
        )

    if ocr_clicked and uploaded is not None:
        if _extract_receipt_from_c is None:
            st.error("没找到 app/ocr/receipt.py 的 extract_receipt，先确认文件在不在。")
        else:
            try:
                # ReceiptError 继承 ValueError：格式不对、不是小票、没 Key 都走这里
                with st.spinner("正在识别这张图…（视觉模型约 3-5 秒）"):
                    result = _extract_receipt_from_c(
                        uploaded.getvalue(), uploaded.type or "image/jpeg"
                    )
            except ValueError as exc:
                st.error(f"识别失败：{exc}")
            else:
                record = _record_from_ocr(result)
                record["_id"] = int(st.session_state.get("rec_draft_seq", 0)) + 1
                st.session_state["rec_draft_seq"] = record["_id"]
                st.session_state["rec_draft"] = record
                st.session_state["rec_parse_state"] = "小票识别（extract_receipt）"
                st.session_state["rec_flash"] = None
                st.session_state["rec_warn"] = None
                _seed_widgets(record)

    draft = st.session_state.get("rec_draft")
    if draft is not None:
        if draft.get("_note"):
            st.caption(f"⚠️ {draft['_note']}")

        edited = render_confirm_card(draft)
        if edited is not None:
            tx_id, warn = _save_record(edited)
            if tx_id is None:
                st.session_state["rec_save_state"] = "会话内暂存（A 的 add_transaction 未接通）"
                saved = st.session_state.get("rec_demo_saved")
                if saved is None:
                    saved = []
                    st.session_state["rec_demo_saved"] = saved
                saved.append(edited)
            else:
                st.session_state["rec_save_state"] = f"A 的 add_transaction（编号 #{tx_id}）"

            st.session_state["rec_pending"] = {
                "drop_draft": True,
                "text": "",
                "flash": _flash_text(edited, tx_id),
                "warn": warn or None,
            }
            st.rerun()

    demo_saved = st.session_state.get("rec_demo_saved") or []
    if demo_saved:
        with st.expander(f"演示模式：本次会话记了 {len(demo_saved)} 笔（没进数据库，刷新即失）"):
            # ⚠️ 这里故意不用 st.dataframe：它要 import pandas，
            #    而这台机器上 numpy.random 的 DLL 被应用控制策略拦了，
            #    pandas 一 import 就 ImportError，整个页面会挂。
            #    手写一张 Markdown 表格，零依赖、够演示。
            lines = ["| 金额 | 类别 | 时间 | 商户 |", "| --- | --- | --- | --- |"]
            for r in demo_saved:
                lines.append(
                    f"| {r['amount']:.2f} | {r['category']} | {r['occurred_at'][:16]} | "
                    f"{r.get('merchant') or '-'} |"
                )
            st.markdown("\n".join(lines))

    # 状态行要如实反映"这次实际走了哪条路"。
    # ⚠️ 不能只看 import 成不成功：B/A 的函数存在但还抛 NotImplementedError，
    #    那样会显示成"已接通"，评审一看没入库就穿帮了。
    parse_state = st.session_state.get("rec_parse_state", "还没解析过")
    save_state = st.session_state.get("rec_save_state", "还没入库过")
    st.caption(f"当前解析：{parse_state} ｜ 入库：{save_state}")
