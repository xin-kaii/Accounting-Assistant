"""主链路端到端自检（Owner: C｜第 5-6 天｜11/26 里程碑）

一句话说清它验什么：

    输入"午饭 25" -> 解析 -> 确认卡片（改成 30）-> add_transaction 入库
    -> list_transactions 查得到 -> 账单页显示

为什么要有这个脚本：
    "我自己电脑上能跑"不算通。评审、队友、以后改坏了，都需要一个**一条命令**能复验的东西。
    它跑在临时数据库上（data/_e2e_check.db），不碰你演示用的 data/app.db。

用法：
    python scripts/check_e2e.py

退出码：0 = 全通，1 = 有失败项（会打印失败在哪一步）
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 必须在 import app.* 之前设置：config 在 import 时读数据库路径
CHECK_DB = ROOT / "data" / "_e2e_check.db"
if CHECK_DB.exists():
    CHECK_DB.unlink()
os.environ["DB_PATH"] = str(CHECK_DB)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.conn import init_db                      # noqa: E402
from app.services.ledger import list_transactions    # noqa: E402
from streamlit.testing.v1 import AppTest             # noqa: E402

FAILS: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(("  ok   " if ok else "  FAIL ") + msg)
    if not ok:
        FAILS.append(msg)


def by_key(elements, key: str):
    for element in elements:
        if getattr(element, "key", None) == key:
            return element
    raise AssertionError(f"找不到控件 {key}")


def main() -> int:
    init_db()
    at = AppTest.from_file(str(ROOT / "app" / "ui" / "main.py"), default_timeout=120).run()
    check(not at.exception, "页面能打开，5 个标签页无异常")

    print("== 1. 输入一句话并解析 ==")
    by_key(at.text_input, "rec_text").set_value("午饭 25，和同事 AA")
    by_key(at.button, "rec_parse").click()
    at.run()
    check(not at.exception, "点『解析』不报错")
    draft = at.session_state.get("rec_draft")
    check(bool(draft), "确认卡片出现了")
    if not draft:
        return 1
    kid = draft["_id"]
    check(draft["amount"] == 25.0, f"金额解析成 25.0（实际 {draft['amount']}）")
    check(draft["category"] == "餐饮", f"类别解析成餐饮（实际 {draft['category']}）")

    print("== 2. 改金额后确认记账 ==")
    by_key(at.number_input, f"rec_{kid}_amount").set_value(30.0)
    at.run()
    by_key(at.button, f"rec_{kid}_save").click()
    at.run()
    check(not at.exception, "点『确认记账』不报错")
    flash = at.session_state.get("rec_flash") or ""
    check("编号" in flash, f"提示里有真实编号（实际：{flash}）")

    print("== 3. 数据库里确实落了这笔 ==")
    rows = list_transactions()
    check(len(rows) == 1, f"数据库 1 笔（实际 {len(rows)}）")
    if rows:
        row = rows[0]
        check(row["amount"] == 30.0, f"金额是用户改后的 30.0（实际 {row['amount']}）")
        check(row["source"] == "text", f"source = text（实际 {row['source']}）")
        check(row["raw_input"] == "午饭 25，和同事 AA", "存下了用户原话 raw_input")

    print("== 4. 账单页能看见 ==")
    at.run()
    page_text = "\n".join(m.value or "" for m in at.markdown)
    metrics = {m.label: m.value for m in at.metric}
    check("¥30.00" in page_text, "账单表格里有 ¥30.00")
    check(metrics.get("笔数") == "1", f"账单页笔数 = 1（实际 {metrics.get('笔数')}）")

    print()
    if FAILS:
        print(f"❌ 主链路没通，{len(FAILS)} 项失败")
        return 1
    print("✅ 主链路端到端通过：输入 → 解析 → 确认 → 入库 → 账单可见")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        # 临时库用完就删，别让它混进演示数据
        if CHECK_DB.exists():
            CHECK_DB.unlink()
    sys.exit(code)
