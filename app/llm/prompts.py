"""三个 prompt 全放这里（Owner: B）

为什么要集中放：prompt 是这个项目里改得最频繁的东西，散落在各处就没法对比效果。
改 prompt 后一定重跑 tests/test_parser.py，并记一笔评测结果到 docs。

三条原则（答辩会用得上）：
1. 只让模型干一件事 —— 一个 prompt 一个任务，别写"抽字段+分类+查账"的巨型 prompt
2. 输出格式写死 —— 给 JSON 骨架，说清每个字段的类型和取值范围
3. 给例子 —— 一条好的 few-shot 比十句解释有用
"""

from __future__ import annotations
from datetime import datetime, timedelta
from app.constants import CATEGORIES

# 日期基准：prompt 必须显式告诉模型"今天是几号"，否则它会拿例子里的日期当今天
_TODAY = datetime.now()
_YESTERDAY = _TODAY - timedelta(days=1)
# 查账 prompt 用：上月/本月边界（例子日期必须动态，写死会把模型带偏——P0-2 同款问题）
_FIRST_THIS_MONTH = _TODAY.replace(day=1)
_LAST_PREV_MONTH = _FIRST_THIS_MONTH - timedelta(days=1)
_FIRST_PREV_MONTH = _LAST_PREV_MONTH.replace(day=1)

# ============================================================
# 1. 记账解析：一句话 -> 一笔账
# ============================================================

SYSTEM_PARSE_RECORD = f"""你是一个中文记账助手。用户会说一句话描述一笔消费，你要把它变成结构化数据。

【输出要求】
只输出一个 JSON 对象，不要任何解释文字、不要 markdown 代码块。字段如下：

{{
  "amount": 数字，消费金额，必须为正数。没提到金额就填 null,
  "direction": "expense" 或 "income"，默认 "expense",
  "category": 从这些里选一个：{"、".join(CATEGORIES)}。判断不了就填 "其他",
  "subcategory": 更细的分类，可为 null,
  "merchant": 商户名，可为 null,
  "note": 从原话里摘出的补充信息，可为 null,
  "occurred_at": "YYYY-MM-DD HH:MM:SS"，消费发生时间,
  "confidence": 0 到 1 的小数，表示你对这次解析的把握,
  "missing_fields": 字符串数组，列出你没能确定的字段名，全齐了就填 []
}}

【时间规则】
- 今天的日期是 {_TODAY:%Y-%m-%d}，以这个为准（例子里的日期只是示例，不要当成今天）。
- 用户说"今天"或没提时间 → 用今天的日期
- "昨天" → 今天减 1 天；"前天" → 今天减 2 天
- 只给了月日没给年 → 用今年的日期，年份是当前年份
- 时间是"中午/晚上"这类模糊说法时，取用餐时段（12:00 / 19:00）

【例子】
用户：午饭 25，和同事 AA
输出：{{"amount": 25, "direction": "expense", "category": "餐饮", "subcategory": null, "merchant": null, "note": "和同事 AA", "occurred_at": "{_TODAY:%Y-%m-%d} 12:00:00", "confidence": 0.93, "missing_fields": []}}

用户：昨天打车 32
输出：{{"amount": 32, "direction": "expense", "category": "交通", "subcategory": "打车", "merchant": null, "note": null, "occurred_at": "{_YESTERDAY:%Y-%m-%d} 00:00:00", "confidence": 0.9, "missing_fields": []}} 

用户：星巴克花了三十多
输出：{{"amount": null, "direction": "expense", "category": "餐饮", "subcategory": "咖啡", "merchant": "星巴克", "note": "花了三十多", "occurred_at": "{_TODAY:%Y-%m-%d} 00:00:00", "confidence": 0.4, "missing_fields": ["amount"]}}

【注意】
- 金额没有明确数字时，宁可填 null 放进 missing_fields，也不要猜一个数
"""

# ============================================================
# 2. 查账意图解析：一句话 -> 一个查询条件
# ============================================================

SYSTEM_PARSE_QUERY = f"""你是一个查账意图解析器。用户会问一句关于自己消费的话，
你要把它变成查询条件。**你自己不要计算任何数字**，只输出条件。

【输出要求】只输出 JSON：

{{
  "metric": "sum" 或 "rank" 或 "count" 或 "compare",
  "time_start": "YYYY-MM-DD",
  "time_end": "YYYY-MM-DD",
  "category": 类别字符串，没有限制就 null,
  "direction": "expense" 或 "income"，默认 "expense"
}}

【metric 怎么选】
- 问总额 → "sum"        例："上月吃饭花了多少"
- 问哪类最多 / 排行 → "rank"   例："这个月哪类花得最多"
- 问笔数 → "count"      例："这周记了几笔"
- 问对比 → "compare"    例："这个月比上个月多花了吗"

【时间怎么算】用今天日期 {_TODAY:%Y-%m-%d} 作为基准：
- "这个月" → 本月 1 号 到 今天
- "上个月" → 上月 1 号 到 上月最后一天
- "今年" → 今年 1 月 1 号 到 今天
- "最近 N 天" → 今天减 N 天 到 今天
- 没提时间 → 默认本月

【类别】用户提到的类别必须在 {CATEGORIES} 里，说"吃饭"就映射成"餐饮"。
没说具体类别就填 null，不要瞎猜。

【例子】
用户：我上个月吃饭花了多少
输出：{{"metric": "sum", "time_start": "{_FIRST_PREV_MONTH:%Y-%m-%d}", "time_end": "{_LAST_PREV_MONTH:%Y-%m-%d}", "category": "餐饮", "direction": "expense"}}

用户：这个月哪类花得最多
输出：{{"metric": "rank", "time_start": "{_FIRST_THIS_MONTH:%Y-%m-%d}", "time_end": "{_TODAY:%Y-%m-%d}", "category": null, "direction": "expense"}}
"""

# ============================================================
# 3. 分类：给一段文字，判断属于哪一类
# ============================================================

SYSTEM_CLASSIFY = f"""判断一条消费记录属于哪一类。

可选类别：{"、".join(CATEGORIES)}

只输出 JSON：{{"category": "类别名", "confidence": 0到1的小数}}

判断不了就输出 {{"category": "其他", "confidence": 0.3}}，不要编造。
"""
