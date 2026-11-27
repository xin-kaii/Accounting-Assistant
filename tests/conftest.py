"""pytest 公共夹具（Owner: A）

放这里的 fixture 所有 test_*.py 都能直接用，不用各自 import。
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

import app.db.conn as conn_mod


@pytest.fixture(scope="session")
def _db_dir():
    """整个 pytest 进程共用一个临时目录，进程结束时删掉。

    不用 pytest 自带的 tmp_path（它会给每个测试开一个目录，
    在这台没设 TEMP 环境变量的 Git Bash 上还会把 pytest-of-xx/ 建到
    项目根目录），就用冒烟测试同款的 tempfile.mkdtemp()。
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="ledger_test_"))
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture()
def db(_db_dir, monkeypatch):
    """每个测试开始前删库重建，保证测试之间不串数据，绝不碰 data/app.db。

    为什么必须重置：比如 test_分类聚合 断言 total 精确等于 1000.0，
    上一个测试留下的账单会让它挂掉。这里直接复用 conn.py 现成的
    reset_db()（它本来就是"删库重建"用的，只是重建的是临时库）。

    为什么用 monkeypatch 而不是直接赋值：setattr 会自动还原——就算某个
    测试中途炸了，DB_PATH 也会被改回原值。直接赋值的话，一旦 fixture
    异常，残留的临时路径会让同一进程里后续不带 db 夹具的 DB 操作
    （比如以后 C 的 test_sample_data.py）静默写错库。

    为什么不用 :memory:：项目的 tx() 每次操作开新连接、用完立刻关
    （防 SQLite 并发锁），内存库的数据会跟着连接一起消失，第二次查询
    就拿不到了，所以必须落在临时文件上。
    """
    monkeypatch.setattr(conn_mod, "DB_PATH", _db_dir / "test.db")
    conn_mod.reset_db()
    yield  # 测试函数在这里运行
