# 测试目录（谁写哪块）

**规则：文件名前缀写模块名，谁的模块谁写，不要改别人的测试文件。**

| 文件 | 谁写 | 测什么 | 什么时候 |
|---|---|---|---|
| `test_ledger.py` | **A** | `add_transaction` 校验、查询时间区间、改删 | 第 12 天 |
| `test_stats.py` | **A** | 分类聚合、月度趋势、空数据不崩 | 第 12 天 |
| `test_budget.py` | **A** | 超支边界：99%、**刚好 100%**、100.01% | 第 12 天 |
| `test_parser.py` | **B** | 20 条语句的金额/类别/时间准确率 | 第 12 天 |
| `test_query_parser.py` | **B** | "上个月/这个月/今年/最近30天" 解析对不对 | 第 12 天 |
| `test_mock_llm.py` | **B** | 离线模式能不能跑通（没 Key 也不崩） | 第 12 天 |
| `test_receipt.py` | **C** | 字段校验、低置信度判定、非账单图片报错 | 第 12 天 |
| `test_sample_data.py` | **C** | 生成的 CSV 列对、日期在最近 3 个月、可重复执行 | 第 12 天 |
| `test_ui_smoke.py` | **D** | 5 个页面 import 不报错、函数签名没变 | 第 12 天 |

## 三条原则（零基础版）

1. **只测纯函数**，不测 UI、不测网络。测 UI 会被 Streamlit 的怪行为折磨死。
2. **不花钱**：调模型的测试全部走 `mock_llm`，或者用 monkeypatch 换掉 `client.chat_json`。
3. **每个测试都要能独立跑**：用内存数据库 `sqlite3.connect(":memory:")`，不碰 `data/app.db`。

## 怎么跑

```bash
pytest -v                      # 全部
pytest tests/test_budget.py    # 只跑预算
pytest -k "100"                # 只跑名字里带 100 的
```

## 最低要求

第 12 天结束时，`pytest` 要能 **全绿**。哪怕每人只有 3 个用例，也比没有强——
评审维度里「是否有基本的测试或自检手段」就是看这个。
