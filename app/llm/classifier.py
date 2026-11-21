"""自动分类（Owner: B｜第 5-6 天完成）

大部分时候 parse_record 已经顺带给了类别，这个函数是"补刀"用的：
用户手动改了备注、或者 OCR 只认出商户名时，用它判断类别。
"""

from __future__ import annotations


def classify(text: str) -> tuple[str, float]:
    """返回 (类别, 置信度)。

    text 可以是商户名、备注、或一整句话。
    返回的类别必须属于 app.constants.CATEGORIES，判断不了就返回 ("其他", 低置信度)。

    实现路径同 parser：
        config.llm_ready() -> client.chat_json(prompts.SYSTEM_CLASSIFY, text)
        否则               -> mock_llm.classify(text)

    TODO(B) 第 5-6 天
    """
    raise NotImplementedError("TODO(B) 第 5-6 天")
