"""薄 FastAPI 接口（Owner: A｜第 9-10 天｜加分项，40 行）

定位：**额外再暴露一层** HTTP 接口，不替换主链路。
     Streamlit 页面继续直接调函数，不改成走 HTTP。

答辩话术：
    "主链路端到端纵向负责，保证零基础 4 人团队能并行；同时额外暴露了一层
     REST 接口，方便后续前后端分离或第三方调用。主链路不依赖这一层。"

三条纪律：
    1. 最多 40 行。写到 100 行说明跑偏了，停手
    2. 只包已有函数，不在这里写业务逻辑
    3. 不影响任何人 —— 这一层挂了，Streamlit 照常跑

启动：uvicorn app.api:app --reload --port 8000
文档：http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="记账助手 API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    """健康检查。评审/容器探活用。"""
    return {"status": "ok"}


# TODO(A) 第 9-10 天：把这三个函数包上
#
# from app.services.ledger import add_transaction
# from app.services.stats import get_stats
# from app.llm.query_parser import parse_query
#
# @app.post("/transactions")
# def api_add(payload: dict):
#     return {"id": add_transaction(payload)}
#
# @app.get("/stats")
# def api_stats(start: str, end: str, category: str | None = None):
#     return get_stats(start, end, category)
#
# @app.post("/query")
# def api_query(payload: dict):
#     return parse_query(payload["question"])
