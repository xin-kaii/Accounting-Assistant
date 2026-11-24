"""账单存取（Owner: A｜第 3-4 天完成）

这是全项目的地基：B 解析出来的、C 识别出来的、页面手动填的，最后都调这里的函数入库。
签名定了就不许改，改了另外三个人全崩。
"""

from __future__ import annotations

from datetime import date, datetime

from app.constants import (
    DEFAULT_CATEGORY,
    DIRECTIONS,
    SOURCE_MANUAL,
    SOURCES,
)
from app.db.conn import DATETIME_FMT, now_str, tx
from app.money import to_cents, to_yuan


def _clean_text(value: object) -> str | None:
    """去空格；空字符串存 NULL。

    三列空值只允许一种写法：页面传 ""、模型传 None，最后库里都得是 NULL。
    否则做 COUNT(merchant) 之类的统计会把一堆空串也算进去。
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_occurred_at(value: object) -> str:
    """统一成 'YYYY-MM-DD HH:MM:SS'。

    三个调用方给的格式不会天然一致，都在这里补全：
        C 的 st.date_input -> date 对象 或 '2026-11-20'
        B 的模型          -> '2026-11-20 12:30'，偶尔带 T 或斜杠
        D 的表单          -> 'YYYY-MM-DD'
    入库后格式统一，「字符串比较 = 时间比较」这条规矩才成立。
    """
    if isinstance(value, datetime):      # datetime 是 date 的子类，先判它
        return value.strftime(DATETIME_FMT)
    if isinstance(value, date):
        return f"{value} 00:00:00"
    text = str(value or "").strip().replace("/", "-").replace("T", " ")
    if len(text) == 10:                  # 只给了日期 -> 补零点
        text += " 00:00:00"
    elif len(text) == 16:                # 少了秒
        text += ":00"
    return text


def _parse_occurred_at(value: object) -> str:
    """归一化 + 校验，返回能直接入库的 'YYYY-MM-DD HH:MM:SS'。"""
    normalized = _normalize_occurred_at(value)
    try:
        datetime.strptime(normalized, DATETIME_FMT)
    except ValueError:
        raise ValueError(
            f"occurred_at 必须是 'YYYY-MM-DD HH:MM:SS'（只给日期也行），收到 {value!r}"
        ) from None
    return normalized


def _parse_amount(value: object) -> int:
    """元 -> 分。None、非数字、<= 0 都抛 ValueError。"""
    if value is None:
        raise ValueError("amount 不能为空")
    try:
        yuan = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"amount 必须是数字，收到 {value!r}") from None
    if yuan <= 0:
        raise ValueError(f"amount 必须大于 0，收到 {yuan}")
    return to_cents(yuan)


def _parse_direction(value: object) -> str:
    if value not in DIRECTIONS:
        raise ValueError(f"direction 只能是 {DIRECTIONS}，收到 {value!r}")
    return value


def _parse_source(value: object) -> str:
    """没传兜 manual，传错报错（默认值兜「没传」，报错兜「传错」）。"""
    source = value or SOURCE_MANUAL
    if source not in SOURCES:
        raise ValueError(f"source 只能是 {SOURCES}，收到 {value!r}")
    return source


def _parse_confidence(value: object) -> float | None:
    """非数字存 NULL；数字夹到 0~1。"""
    if value is None:
        return None
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    return min(1.0, max(0.0, confidence))


def _row_to_dict(row) -> dict:
    """库里的行 -> 给页面用的 dict。

    金额同时给两份：
        amount       元（float），页面直接显示
        amount_cents 分（int），页面做小计 / 合计时用它做整数累加，
                     不会踩 "0.1 + 0.2 = 0.30000000000000004" 这种浮点误差
    """
    item = dict(row)
    item["amount_cents"] = item["amount"]
    item["amount"] = to_yuan(item["amount_cents"])
    return item


def add_transaction(record: dict) -> int:
    """存一笔账，返回新的 id。

    record 必填：
        occurred_at : 'YYYY-MM-DD HH:MM:SS'  钱是什么时候花的
                      也收 'YYYY-MM-DD'、'YYYY-MM-DD HH:MM'、date / datetime 对象，
                      入库前统一补成全格式（页面只给日期时不会报错）
        amount      : float > 0               金额，**单位：元**（如 25.5）
                                              入库时用 money.to_cents() 转成分存储
        direction   : 'expense' | 'income'

    record 选填（缺了用默认值）：
        category    : 默认 "其他"（空白字符串也算没传）
        subcategory / merchant / note : 默认 None（空白字符串一律存 NULL）
        source      : 默认 "manual"（C 的页面应该显式传 text/receipt/manual）
        raw_input   : 默认 None（C 的页面传用户原话或 OCR 原文）
        confidence  : 默认 None（非数字存 NULL，超出 0~1 夹到边界）

    raise ValueError：下面四种情况都要抛，不要静默兜底
        1. amount <= 0
        2. direction 不是 expense / income
        3. occurred_at 是空值、或真解析不出来（"昨天"这种）
        4. source 传了非法值（比如 "abc"）—— 这一条最容易漏：
           如果把它悄悄改成 "manual"，C 写错了也没人知道，
           答辩统计「三种录入方式各占多少」时就分不出来了。
           口径：默认值兜「没传」，报错兜「传错」。

    TODO(A) 第 3-4 天
    """
    # ---------- 1. 必填三项：时间 / 金额 / 方向 ----------
    occurred_at = _parse_occurred_at(record.get("occurred_at"))
    amount_cents = _parse_amount(record.get("amount"))
    direction = _parse_direction(record.get("direction"))

    # ---------- 2. 来源：没传就兜默认，传错就报错 ----------
    source = _parse_source(record.get("source"))

    # ---------- 3. 置信度：模型偶尔返回 "高"，宁可存 NULL，也别让 REAL 列里躺字符串 ----------
    confidence = _parse_confidence(record.get("confidence"))

    # ---------- 4. 入库（金额转成分） ----------
    with tx() as conn:
        cur = conn.execute(
            """
            INSERT INTO transactions
                (occurred_at, amount, direction, category, subcategory,
                 merchant, note, source, raw_input, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                occurred_at,
                amount_cents,
                direction,
                _clean_text(record.get("category")) or DEFAULT_CATEGORY,
                _clean_text(record.get("subcategory")),
                _clean_text(record.get("merchant")),
                _clean_text(record.get("note")),
                source,
                _clean_text(record.get("raw_input")),
                confidence,
                now_str(),
            ),
        )
        return int(cur.lastrowid)


def list_transactions(
    start: str | None = None,
    end: str | None = None,
    category: str | None = None,
    direction: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """按条件查账单，按 occurred_at 倒序（最新的在前）。

    start / end 都是 'YYYY-MM-DD'，闭区间（含当天）。
    category / direction 传 None 或空串表示不筛；direction 会去空格并忽略大小写。
    limit 会被夹到 1~1000（传 0 或负数不会是「不限」）。

    返回的每行 = 表里的全部列，其中：
        amount       元（float），页面直接显示
        amount_cents 分（int），页面做小计 / 合计时用它做整数累加
    账单列表页、对话页都调它。

    TODO(A) 第 3-4 天
    """
    sql = "SELECT * FROM transactions WHERE 1 = 1"
    params: list[object] = []

    # 闭区间：start 从当天 00:00:00 起，end 到当天 23:59:59 止
    if start:
        sql += " AND occurred_at >= ?"
        params.append(f"{start} 00:00:00")
    if end:
        sql += " AND occurred_at <= ?"
        params.append(f"{end} 23:59:59")
    if category is not None and str(category).strip():
        sql += " AND category = ?"
        params.append(str(category).strip())
    if direction is not None and str(direction).strip():
        # 筛选是「读」，宽容一点：' Income ' 也认。
        # 不这么做的话，页面传个带空格的值就静默查出空列表，很难查。
        direction = str(direction).strip().lower()
        if direction not in DIRECTIONS:
            raise ValueError(f"direction 只能是 {DIRECTIONS}，收到 {direction!r}")
        sql += " AND direction = ?"
        params.append(direction)

    sql += " ORDER BY occurred_at DESC, id DESC LIMIT ?"
    # SQLite 里 LIMIT -1 等于「不限」，页面传 0/负数时不能把全表拉出来
    params.append(max(1, min(int(limit), 1000)))

    with tx() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [_row_to_dict(row) for row in rows]


def get_transaction(tx_id: int) -> dict | None:
    """查单条，不存在返回 None。

    返回结构和 list_transactions 的每行一样（amount 元 + amount_cents 分）。
    D 的"编辑账单"弹窗用它把原值填进输入框。
    """
    with tx() as conn:
        row = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
    return _row_to_dict(row) if row else None


# update_transaction 允许改的列。白名单而不是黑名单：新加字段时默认不可改，安全。
_UPDATABLE = (
    "occurred_at",
    "amount",
    "direction",
    "category",
    "subcategory",
    "merchant",
    "note",
    "source",
    "raw_input",
    "confidence",
)


def update_transaction(tx_id: int, **fields) -> bool:
    """改一条（用户在确认页改了金额/类别后调用）。返回是否改成功。

    只认 _UPDATABLE 里的列，amount 仍然传「元」（和 add_transaction 一致），
    内部转成分再写库。传别的字段（拼错的 amout、想改 id/created_at）直接
    ValueError —— 悄悄忽略的话，页面以为改好了，其实没改，最难查。

    一个字段都没传 -> 返回 False（用户点保存但没动任何东西）。
    记录不存在 -> 返回 False（rowcount = 0）。

    改过之后，B 会把 (raw_input, 错的, 对的) 写进 corrections 表（record_correction）。
    """
    unknown = set(fields) - set(_UPDATABLE)
    if unknown:
        raise ValueError(f"update_transaction 不能改这些字段：{sorted(unknown)}")

    assignments: list[str] = []
    params: list[object] = []
    for field, value in fields.items():
        if field == "occurred_at":
            params.append(_parse_occurred_at(value))
        elif field == "amount":
            params.append(_parse_amount(value))
        elif field == "direction":
            params.append(_parse_direction(value))
        elif field == "source":
            params.append(_parse_source(value))
        elif field == "confidence":
            params.append(_parse_confidence(value))
        elif field == "category":
            params.append(_clean_text(value) or DEFAULT_CATEGORY)
        else:
            params.append(_clean_text(value))
        assignments.append(f"{field} = ?")   # field 来自白名单，不是用户拼进来的

    if not assignments:
        return False

    with tx() as conn:
        cur = conn.execute(
            f"UPDATE transactions SET {', '.join(assignments)} WHERE id = ?",
            (*params, tx_id),
        )
        return cur.rowcount > 0


def delete_transaction(tx_id: int) -> bool:
    """删一条。记录不存在返回 False。"""
    with tx() as conn:
        cur = conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        return cur.rowcount > 0


def record_correction(raw_input: str, wrong: dict, correct: dict) -> None:
    """记一次用户修正，给 B 的 prompt 当 few-shot 例子用（加分项，第 10 天后有空再做）。"""
    raise NotImplementedError("TODO(A) 加分项，可跳过")
