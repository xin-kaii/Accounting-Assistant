"""大模型客户端（Owner: B｜第 3-4 天完成）

三个要求，缺一个后面全崩：
1. 超时：默认 30 秒，别让页面卡死
2. 重试：JSON 解析失败时重试 1 次（把错误告诉模型让它重出）
3. 兜底：两次都失败就抛 LLMError，调用方决定退到 mock_llm

用 openai 这个 SDK 调所有家（DeepSeek/千问/智谱都兼容），只改 base_url。
"""

from __future__ import annotations

import json
from typing import Any

from app import config


class LLMError(Exception):
    """模型调用失败（超时、没 Key、返回的不是 JSON）。"""


def chat_json(
    system_prompt: str,
    user_content: str,
    *,
    model: str | None = None,
    timeout: float = 30.0,
    retry: int = 1,
) -> dict[str, Any]:
    """让模型返回一个 JSON 对象。

    参数：
        system_prompt : 角色 + 输出格式要求
        user_content  : 用户的原话
        model         : 不传就用 config.LLM_MODEL
        retry         : JSON 解析失败时重试几次

    返回：dict

    raise LLMError：
        - 没配 Key（config.llm_ready() 为 False）
        - 网络超时
        - 重试完还是解析不出 JSON

    实现提示：
        1. 用 openai.OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
        2. 请求里加 response_format={"type": "json_object"}，
           DeepSeek 和千问都支持，能大幅提高出 JSON 的概率
        3. json.loads 外面套 try；失败就把"你上次返回的不是合法 JSON"追加成
           一条 user 消息再试一次
        4. 别在这里做业务判断，这里只负责"拿到一个 dict"

    TODO(B) 第 3-4 天
    """
    if not config.llm_ready():
        raise LLMError("未配置 LLM_API_KEY，或 USE_MOCK_LLM=true")
    raise NotImplementedError("TODO(B) 第 3-4 天")


def chat_vision(
    system_prompt: str,
    image_bytes: bytes,
    user_text: str = "请识别这张小票/截图里的消费信息",
    *,
    model: str | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """让视觉模型看一张图，返回 JSON。

    给 C 用。图片转 base64 塞进 image_url（data URI 格式）。

    raise LLMError：没配 VLM_API_KEY / 超时 / 返回的不是 JSON

    TODO(B) 第 5 天（或 C 直接用 openai SDK 自己写，两人商量）
    """
    if not config.vlm_ready():
        raise LLMError("未配置 VLM_API_KEY")
    raise NotImplementedError("TODO(B/C) 第 5 天")
