"""查账意图解析（Owner: B｜第 7-8 天完成）

这是 MVP 第 3 项的核心，也是答辩最容易加分的地方。

⭐ 关键设计（答辩必讲）：
   模型**只输出查询条件，不输出数字**。金额由 A 的 SQL 去数据库里算。
   题目原文要求"需要真正解析时间范围与类别，而不是把问题原样丢给模型自由回答"，
   指的就是这个做法。

   反过来做（让模型看着账单列表自己算）会犯两个错：
   1. 数字会错（模型不擅长算术）
   2. 账单有 100 多条时根本塞不进 prompt
"""

from __future__ import annotations

from app import config
from app.llm import client, mock_llm, prompts


def parse_query(text: str) -> dict:
    """把一句话问句解析成查询条件（不含任何计算结果）。

    返回：
    {
        "metric": "sum" | "rank" | "count" | "compare",
        "time_start": "2026-10-01",
        "time_end": "2026-10-31",
        "category": "餐饮" 或 None,
        "direction": "expense",
    }

    raise ValueError：完全听不懂时抛这个，让 B 的对话页提示
                     "没听懂这个问题，试试『上个月吃饭花了多少』"

    TODO(B) 第 7-8 天
    """
    raise NotImplementedError("TODO(B) 第 7-8 天")


def answer_query(text: str) -> str:
    """可选：把查询结果组织成一句人话回复。

    流程：parse_query(text) -> A 的 get_stats() -> 把数字拼成中文句子。
    ⚠️ 数字必须来自 get_stats() 的返回值，不许由模型生成。

    TODO(B) 第 9-10 天
    """
    raise NotImplementedError("TODO(B) 第 9-10 天")
