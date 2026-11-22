"""配置读取（Owner: A）

所有密钥都从 .env 读，代码里不许出现明文 Key。
.env.example 是模板；.env 是自己填的（已在 .gitignore 里）。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录（app/ 的上一级）
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    """读环境变量，去掉首尾空格。"""
    return (os.getenv(key) or default).strip()


# ---------- 数据库 ----------
# 相对路径按项目根目录算，避免从不同目录启动时找不到库
_db = _env("DB_PATH", "data/app.db")
DB_PATH = Path(_db) if Path(_db).is_absolute() else ROOT / _db

# ---------- 文本模型（B 用）----------
LLM_BASE_URL = _env("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_API_KEY = _env("LLM_API_KEY")
LLM_MODEL = _env("LLM_MODEL", "deepseek-chat")

# ---------- 视觉模型（C 用）----------
VLM_BASE_URL = _env("VLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
VLM_API_KEY = _env("VLM_API_KEY")
VLM_MODEL = _env("VLM_MODEL", "qwen-vl-max")

# ---------- 开关 ----------
# true 时不调真模型，走 app/llm/mock_llm.py 的离线规则（没网/没额度也能演示）
USE_MOCK_LLM = _env("USE_MOCK_LLM", "false").lower() in ("1", "true", "yes")

# 占位符标记：.env.example 里写的是「你的key」，如果用户没改就复制成 .env，
# 这些值必须被当成"未配置"，否则程序会拿着假 Key 去调接口，报 401 而不是降级。
_PLACEHOLDER_MARKERS = ("你的", "填", "your", "xxx", "placeholder", "todo")


def _is_placeholder(value: str) -> bool:
    v = (value or "").strip().lower()
    if not v:
        return True
    return any(m in v for m in _PLACEHOLDER_MARKERS)


def _configured(value: str) -> bool:
    """有值且不是占位符，才算真的配好了。"""
    return bool(value) and not _is_placeholder(value)


def llm_ready() -> bool:
    """文本模型是否可用。未配 Key 或仍是占位符时自动走离线模式。"""
    return _configured(LLM_API_KEY) and not USE_MOCK_LLM


def vlm_ready() -> bool:
    """视觉模型是否可用。未配置时图片识别会返回明确错误，不会崩。"""
    return _configured(VLM_API_KEY)
