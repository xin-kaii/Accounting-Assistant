"""检查文本模型和视觉模型是否真的可用（B / C / 演示机都该跑一次）

用法：
    .venv\\Scripts\\python.exe scripts\\check_models.py
    .venv\\Scripts\\python.exe scripts\\check_models.py samples\\receipts\\a.jpg

它会做三件事：
  1. 打印当前配置（不打印 Key）
  2. 用一句话测文本模型，要求返回 JSON
  3. 传一张图测视觉模型（没给图就跳过）

输出刻意只用 ASCII，避免 Windows 控制台中文乱码。
不通过时返回非 0 退出码，方便以后被 CI 或别的脚本调用。
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import config  # noqa: E402

TEXT_PROMPT = (
    "\u4f60\u662f\u8bb0\u8d26\u52a9\u624b\u3002\u53ea\u8f93\u51fa\u4e00\u4e2a JSON \u5bf9\u8c61\uff0c"
    "\u4e0d\u8981\u89e3\u91ca\u3001\u4e0d\u8981 markdown\u3002\n"
    "\u5b57\u6bb5\uff1aamount \u6570\u5b57\uff1bcategory \u53d6\u503c\u9650\u4e8e\uff1a"
    "\u9910\u996e \u4ea4\u901a \u8d2d\u7269 \u5a31\u4e50 \u5c45\u4f4f \u533b\u7597 \u6559\u80b2 \u901a\u8baf \u4eba\u60c5 \u5176\u4ed6\n"
    "\u4f8b\u5b50\uff1a\u300c\u5348\u996d25\u5757\u300d-> {\"amount\": 25, \"category\": \"\u9910\u996e\"}"
)

VISION_PROMPT = (
    "\u8fd9\u662f\u4e00\u5f20\u5c0f\u7968\u6216\u652f\u4ed8\u622a\u56fe\u3002\u53ea\u8f93\u51fa\u4e00\u4e2a JSON \u5bf9\u8c61\uff1a\n"
    "{\"amount\": \u91d1\u989d\u6570\u5b57, \"date\": \"YYYY-MM-DD\", \"merchant\": \"\u5546\u6237\u540d\"}\n"
    "\u8ba4\u4e0d\u51fa\u7684\u5b57\u6bb5\u586b null\uff0c\u4e0d\u8981\u731c\u3002"
)


def _client(prefix: str):
    from openai import OpenAI

    return OpenAI(
        base_url=getattr(config, f"{prefix}_BASE_URL"),
        api_key=getattr(config, f"{prefix}_API_KEY"),
        timeout=40.0,
        max_retries=1,
    )


def check_config() -> bool:
    print("[1/3] config")
    print(f"  LLM_MODEL   = {config.LLM_MODEL}")
    print(f"  LLM_BASE    = {config.LLM_BASE_URL}")
    print(f"  VLM_MODEL   = {config.VLM_MODEL}")
    print(f"  VLM_BASE    = {config.VLM_BASE_URL}")
    print(f"  llm_ready   = {config.llm_ready()}")
    print(f"  vlm_ready   = {config.vlm_ready()}")
    print(f"  mock_mode   = {config.USE_MOCK_LLM}")
    return config.llm_ready()


def check_text() -> bool:
    print("\n[2/3] text model")
    if not config.llm_ready():
        print("  SKIP  llm_ready is False (Key missing or placeholder)")
        return False
    try:
        resp = _client("LLM").chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": TEXT_PROMPT},
                {"role": "user", "content": "\u5348\u996d25\u5757"},
            ],
            temperature=0,
            max_tokens=80,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        ok = data.get("amount") == 25
        print(f"  {'OK  ' if ok else 'WARN'}  amount={data.get('amount')}  category={data.get('category')}")
        print(f"        raw={resp.choices[0].message.content[:120]}")
        return ok
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL  {type(exc).__name__}: {str(exc)[:160]}")
        return False


def check_vision(image_path: str | None) -> bool:
    print("\n[3/3] vision model")
    if not config.vlm_ready():
        print("  SKIP  vlm_ready is False (Key missing or placeholder)")
        return False
    if not image_path:
        print("  SKIP  no image given")
        print("        put a receipt photo under samples/receipts/ and rerun:")
        print("        python scripts/check_models.py samples/receipts/your.jpg")
        return False
    p = Path(image_path)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        print(f"  FAIL  image not found: {p}")
        return False

    try:
        b64 = base64.b64encode(p.read_bytes()).decode()
        resp = _client("VLM").chat.completions.create(
            model=config.VLM_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                }
            ],
            temperature=0,
            max_tokens=200,
        )
        content = resp.choices[0].message.content
        print(f"  OK    raw={content[:180]}")
        try:
            data = json.loads(content)
            print(f"        parsed amount={data.get('amount')} date={data.get('date')} merchant={data.get('merchant')}")
        except json.JSONDecodeError:
            print("        WARN  not pure JSON, will need cleanup in code")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL  {type(exc).__name__}: {str(exc)[:160]}")
        return False


def main() -> int:
    image = sys.argv[1] if len(sys.argv) > 1 else None
    cfg_ok = check_config()
    text_ok = check_text()
    vis_ok = check_vision(image)

    print("\n=== summary ===")
    print(f"  config : {'OK' if cfg_ok else 'NEED FIX'}")
    print(f"  text   : {'OK' if text_ok else 'FAIL/SKIP'}")
    print(f"  vision : {'OK' if vis_ok else 'FAIL/SKIP'}")
    return 0 if text_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
