"""数据库连接管理（Owner: A）

三条规矩：
1. 每次操作开一个新连接，用完立刻关（SQLite 并发写会报 database is locked）
2. 查询结果用 sqlite3.Row，可以按列名取值：row["amount"]
3. 时间统一存文本，格式 'YYYY-MM-DD HH:MM:SS'，这样字符串比较就等于时间比较

测试时会用内存数据库替换 DB_PATH，所以不要在这里缓存连接。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from app.config import DB_PATH

SCHEMA_FILE = Path(__file__).with_name("schema.sql")

# 统一的时间格式，全项目共用，别各写各的
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"
MONTH_FMT = "%Y-%m"


def now_str() -> str:
    """当前时间，字符串形式。入库统一用它。"""
    return datetime.now().strftime(DATETIME_FMT)


def month_of(dt_str: str) -> str:
    """'2026-11-20 12:30:00' -> '2026-11'"""
    return dt_str[:7]


def get_conn(db_path: str | Path | None = None) -> sqlite3.Connection:
    """开一个新的数据库连接。调用方负责关闭（或直接用 tx()）。"""
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row      # 可以按列名取值
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def tx(db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    """事务上下文：正常结束自动提交，出异常自动回滚，最后一定关闭。

    用法：
        with tx() as conn:
            conn.execute("INSERT INTO ...")
    """
    conn = get_conn(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str | Path | None = None) -> None:
    """建表。重复执行是安全的（schema.sql 里全是 IF NOT EXISTS）。"""
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    with tx(db_path) as conn:
        conn.executescript(sql)


def reset_db(db_path: str | Path | None = None) -> None:
    """删库重建。⚠️ 只在本地调试用，不要在演示前手滑。
    """
    path = Path(db_path) if db_path else DB_PATH
    if path.exists():
        path.unlink()
    init_db(db_path)


if __name__ == "__main__":
    # 直接运行本文件 = 初始化数据库
    init_db()
    print(f"数据库已初始化：{DB_PATH}")
