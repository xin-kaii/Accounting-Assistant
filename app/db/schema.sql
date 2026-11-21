-- 建表脚本（Owner: A）
-- 三张表，字段定义见 docs/分工与排期.md 第 4 节，不许私自加字段。
-- 初始化命令：python -c "from app.db.conn import init_db; init_db()"

-- ============================================================
-- 表 1：账单表（最重要）
-- ============================================================
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 钱是什么时候花的（不是什么时候存进来的！用户可能今天补记昨天的账）
    occurred_at TEXT    NOT NULL,

    amount      REAL    NOT NULL CHECK (amount > 0),   -- 正数，方向看 direction
    direction   TEXT    NOT NULL CHECK (direction IN ('expense', 'income')),
    category    TEXT    NOT NULL,
    subcategory TEXT,
    merchant    TEXT,
    note        TEXT,

    -- 从哪进来的：text / receipt / manual
    source      TEXT    NOT NULL DEFAULT 'manual'
                        CHECK (source IN ('text', 'receipt', 'manual')),

    -- 用户原话，排查问题时用得上（例："午饭25，和同事AA"）
    raw_input   TEXT,
    confidence  REAL,                                  -- 识别置信度 0~1，手动填的为 NULL

    -- 这条记录什么时候存进来的
    created_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tx_occurred  ON transactions (occurred_at);
CREATE INDEX IF NOT EXISTS idx_tx_category  ON transactions (category);
CREATE INDEX IF NOT EXISTS idx_tx_direction ON transactions (direction);

-- ============================================================
-- 表 2：预算表
-- ============================================================
-- ⚠️ category 用空字符串 '' 表示"总预算"，不用 NULL。
--    原因：SQLite 里 NULL 和 NULL 不算相等，UNIQUE 约束拦不住重复插入。
--    这是答辩时会被问到的坑，记住这个理由。
CREATE TABLE IF NOT EXISTS budgets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    month      TEXT    NOT NULL,                        -- 'YYYY-MM'
    category   TEXT    NOT NULL DEFAULT '',             -- '' = 总预算
    amount     REAL    NOT NULL CHECK (amount >= 0),
    created_at TEXT    NOT NULL,
    UNIQUE (month, category)                            -- 同一个月同一类别只能有一条
);

-- ============================================================
-- 表 3：修正记录表（"越记越准"，加分项，做不完可以先不做）
-- ============================================================
-- 用法：用户改过 AI 的识别结果后，把(原话, 错的, 对的)存下来，
--       下次遇到类似原话，把它当 few-shot 例子塞进 prompt。
CREATE TABLE IF NOT EXISTS corrections (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_input    TEXT NOT NULL,
    wrong_json   TEXT,
    correct_json TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
