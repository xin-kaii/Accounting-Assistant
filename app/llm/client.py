"""大模型客户端（Owner: B｜第 3-4 天完成）

三个要求，缺一个后面全崩：
1. 超时：默认 30 秒，别让页面卡死
2. 重试：JSON 解析失败时重试 1 次（把错误告诉模型让它重出）
3. 兜底：两次都失败就抛 LLMError，调用方决定退到 mock_llm

用 openai 这个 SDK 调所有家（DeepSeek/千问/智谱都兼容），只改 base_url。

⭐ 以下三条是 2026-11-22 用智谱 glm-4-flash 实测出来的，照着做能少踩两个坑：

1. **必须传 `response_format={"type": "json_object"}`**
   不传的话模型会返回「一段解释 + markdown 代码块里的 JSON」，
   直接 `json.loads` 必炸。传了之后输出是纯 JSON。

2. **prompt 里列分类枚举时不要用方括号**
   写 `从[餐饮,交通,...]中选一个` 会让模型输出一个全是 null 的数组。
   正确写法是把选项用空格隔开：「餐饮 交通 购物 娱乐 居住 医疗 教育 通讯 人情 其他」

3. **模型会「猜」金额，必须显式禁止**
   输入「星巴克花了三十多」，它会给 `amount: 30` 而不是 `null`。
   prompt 里要写明「没有确切数字就填 null，不要猜」，
   并且在代码里做后校验——否则库里会出现用户没确认过的假数字。
"""

from __future__ import annotations

import json
import re
from typing import Any

from app import config


class LLMError(Exception):
    """模型调用失败（超时、没 Key、返回的不是 JSON）。"""


def _extract_json_object(text: str) -> dict[str, Any]:
    """把模型返回尽量解析成 JSON 对象；解析不出抛 ValueError。"""
    cleaned = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if m:
        cleaned = m.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start:end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("解析结果不是 JSON 对象")
    return data


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

    实现见下方。
    """
    if not config.llm_ready():
        raise LLMError("未配置 LLM_API_KEY，或 USE_MOCK_LLM=true")

    # 延迟导入：离线演示（mock）时即使没装 openai 也不会在 import 阶段崩
    from openai import OpenAI

    model = model or config.LLM_MODEL
    openai_client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    use_response_format = True
    last_raw = ""
    last_err: Exception | None = None
    for attempt in range(retry + 1):
        # 重试时把上次的坏输出反馈给模型，让它重新只出 JSON
        if attempt > 0:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "你上一次的输出无法解析成 JSON，请重新只输出一个合法的 JSON 对象，"
                        "不要任何解释文字、不要 markdown 代码块。"
                        f"上一次的输出是：{last_raw[:500]}"
                    ),
                }
            )
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "timeout": timeout,
        }
        if use_response_format:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = openai_client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or ""
            last_raw = content
            return _extract_json_object(content)
        except Exception as exc:  # noqa: BLE001 —— 统一转 LLMError，让调用方决定是否降级
            last_err = exc
            err_text = str(exc).lower()
            # 模型/网关不支持 response_format 时，去掉它再试，改用 prompt 约束 JSON
            if use_response_format and ("response_format" in err_text or "json_object" in err_text):
                use_response_format = False

    raise LLMError(f"调用模型失败或返回非法 JSON：{last_err}") from last_err


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
