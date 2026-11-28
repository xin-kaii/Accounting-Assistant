"""薄 FastAPI 接口的单元测试（Owner: A）

tests/README.md 的分工表里没单列 api（表是加分项砍掉时写的），
按"谁的模块谁写"补在这里。跑法：pytest tests/test_api.py -v

用 fastapi 的 TestClient 直接调 app，不真起端口；db 夹具把 DB_PATH
指到临时库（conftest），接口和测试跑在同一个进程里，天然生效。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import app


def _client() -> TestClient:
    return TestClient(app)


def test_健康检查(db):
    resp = _client().get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_记账到查账_一条链路(db):
    client = _client()

    added = client.post(
        "/transactions",
        json={"occurred_at": "2026-11-05 12:00:00", "amount": 25.5,
              "direction": "expense", "category": "餐饮"},
    )
    assert added.status_code == 200 and isinstance(added.json()["id"], int)

    rows = client.get("/transactions", params={"start": "2026-11-01", "end": "2026-11-30"})
    assert rows.status_code == 200
    assert rows.json()[0]["amount"] == 25.5 and rows.json()[0]["amount_cents"] == 2550

    one = client.get(f"/transactions/{added.json()['id']}")
    assert one.status_code == 200 and one.json()["category"] == "餐饮"


def test_参数不合法_返回400而不是500(db):
    resp = _client().post(
        "/transactions",
        json={"occurred_at": "昨天", "amount": 5, "direction": "expense"},
    )

    assert resp.status_code == 400
    assert "occurred_at" in resp.json()["detail"]


def test_查不存在的账单_返回404(db):
    assert _client().get("/transactions/999").status_code == 404


def test_局部修改和删除(db):
    client = _client()
    tx_id = client.post(
        "/transactions",
        json={"occurred_at": "2026-11-05 12:00:00", "amount": 25.0, "direction": "expense"},
    ).json()["id"]

    updated = client.patch(f"/transactions/{tx_id}", json={"amount": 30.0})
    assert updated.json()["updated"] is True
    assert client.get(f"/transactions/{tx_id}").json()["amount_cents"] == 3000

    # 白名单外的字段：服务层抛 ValueError -> 400
    assert client.patch(f"/transactions/{tx_id}", json={"amout": 1.0}).status_code == 400

    deleted = client.delete(f"/transactions/{tx_id}")
    assert deleted.json()["deleted"] is True
    assert client.get(f"/transactions/{tx_id}").status_code == 404


def test_统计与预算端点(db):
    client = _client()
    client.post(
        "/transactions",
        json={"occurred_at": "2026-11-15 12:00:00", "amount": 920.0,
              "direction": "expense", "category": "餐饮"},
    )

    stats = client.get("/stats", params={"start": "2026-11-01", "end": "2026-11-30"})
    assert stats.json()["total"] == 920.0 and stats.json()["count"] == 1

    saved = client.post(
        "/budgets",
        json={"month": "2026-11", "amount": 800, "category": "餐饮"},  # JSON body（Pydantic 模型）
    )
    assert saved.status_code == 200 and saved.json()["ok"] is True
    # amount 类型不对：Pydantic 在进服务层之前就挡掉，返回 422
    assert client.post("/budgets", json={"month": "2026-11", "amount": "很多"}).status_code == 422

    check = client.get("/budgets/2026-11/check")
    assert check.json()[0]["level"] == "over" and check.json()[0]["ratio"] == 1.15

    # 月份格式不对也要 400
    assert client.get("/budgets/2026年11月/check").status_code == 400

    deleted = client.delete("/budgets/2026-11", params={"category": "餐饮"})
    assert deleted.json()["deleted"] is True


def test_记账带契约外字段_400而不是静默忽略(db):
    # 服务层白名单（add_transaction）+ ValueError→400：拼错的字段不能被悄悄吞掉
    resp = _client().post(
        "/transactions",
        json={"occurred_at": "2026-11-05 12:00:00", "amount": 5.0,
              "direction": "expense", "amout": 99.0},
    )
    assert resp.status_code == 400
    assert "amout" in resp.json()["detail"]


def test_0元预算超支_ratio的inf_返回200和合法JSON(db):
    # 服务层契约：0 元预算 + 有支出 -> ratio = inf（预算页靠它显示 ∞）。
    # 但 JSON 标准不允许 Infinity，响应层统一转 null，绝不能 500。
    client = _client()
    client.post("/budgets", json={"month": "2026-11", "amount": 0, "category": "通讯"})
    client.post(
        "/transactions",
        json={"occurred_at": "2026-11-05 12:00:00", "amount": 30.0,
              "direction": "expense", "category": "通讯"},
    )

    resp = client.get("/budgets/2026-11/check")

    assert resp.status_code == 200
    row = resp.json()[0]
    assert row["level"] == "over" and row["ratio"] is None
