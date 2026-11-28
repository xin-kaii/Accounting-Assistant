"""薄 FastAPI 接口（Owner: A｜第 9-10 天｜加分项）

定位：**额外再暴露一层** HTTP 接口，不替换主链路。
     Streamlit 页面继续直接调函数，不改成走 HTTP。

答辩话术：
    "主链路端到端纵向负责，保证零基础 4 人团队能并行；同时额外暴露了一层
     REST 接口，方便后续前后端分离或第三方调用。主链路不依赖这一层。"

三条纪律：
    1. 越薄越好：12 个端点全部是**参数转发**，不写任何业务逻辑——
       全文约 70 行代码（其余约 70 行是给队友和评审看的文档注释）；
       判断跑偏的标准不是行数，而是"路由函数里出现了判断或计算"
    2. 只包已有函数，不在这里写业务逻辑
    3. 不影响任何人 —— 这一层挂了，Streamlit 照常跑

启动：uvicorn app.api:app --reload --port 8000（或 python -m app.api）
文档：http://127.0.0.1:8000/docs
⚠️ 容器里只有 Streamlit（8501 单进程），API 不在 Docker 里——
   这是刻意保持的薄：要演示接口就在宿主机跑上面那行命令，别指望 compose 起两个服务。
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.budget import check_budget, delete_budget, get_budgets, set_budget
from app.services.ledger import (
    add_transaction,
    delete_transaction,
    get_transaction,
    list_transactions,
    update_transaction,
)
from app.services.stats import compare_months, get_stats

app = FastAPI(title="记账助手 API", version="0.1.0")


@app.exception_handler(ValueError)
async def _bad_request(request, exc: ValueError):
    """服务层的 ValueError（金额/日期/类别不合法）统一映射成 400，别漏成 500。"""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict:
    """健康检查。评审/容器探活用。"""
    return {"status": "ok"}


# ---------- 账单 ----------

@app.post("/transactions")
def api_add(payload: dict) -> dict:
    """记一笔。字段校验全在 add_transaction 里，这里只转发。"""
    return {"id": add_transaction(payload)}


@app.get("/transactions")
def api_list(
    start: str | None = None,
    end: str | None = None,
    category: str | None = None,
    direction: str | None = None,
    limit: int = 100,
) -> list[dict]:
    return list_transactions(start, end, category, direction, limit)


@app.get("/transactions/{tx_id}")
def api_get(tx_id: int) -> dict:
    row = get_transaction(tx_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"账单 {tx_id} 不存在")
    return row


@app.patch("/transactions/{tx_id}")
def api_update(tx_id: int, fields: dict) -> dict:
    """局部修改（传 {"amount": 30} 这样的字典，字段白名单在服务层）。"""
    return {"updated": update_transaction(tx_id, **fields)}


@app.delete("/transactions/{tx_id}")
def api_delete(tx_id: int) -> dict:
    return {"deleted": delete_transaction(tx_id)}


# ---------- 统计 / 预算 ----------

@app.get("/stats")
def api_stats(start: str, end: str, category: str | None = None) -> dict:
    return get_stats(start, end, category)


@app.get("/stats/compare")
def api_compare(a: str, b: str) -> dict:
    return compare_months(a, b)


@app.get("/budgets/{month}")
def api_budgets(month: str) -> list[dict]:
    return get_budgets(month)


@app.get("/budgets/{month}/check")
def api_budget_check(month: str) -> list[dict]:
    """某月预算执行情况（ok / warn / over 三档）。"""
    return check_budget(month)


class BudgetIn(BaseModel):
    """POST /budgets 的请求体（Pydantic 校验 amount 类型，月份格式仍由服务层管）。"""

    month: str
    amount: float
    category: str = ""  # 缺省 = 总预算


@app.post("/budgets")
def api_set_budget(budget: BudgetIn) -> dict:
    set_budget(budget.month, budget.amount, budget.category)
    return {"ok": True, "month": budget.month, "category": budget.category, "amount": budget.amount}


@app.delete("/budgets/{month}")
def api_delete_budget(month: str, category: str = "") -> dict:
    return {"deleted": delete_budget(month, category)}


# ---------- 查账（B 的 parse_query 实现后，去掉注释即可） ----------
#
# @app.post("/query")
# def api_query(payload: dict) -> dict:
#     return parse_query(payload["question"])


if __name__ == "__main__":  # python -m app.api
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
