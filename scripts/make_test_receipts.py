"""生成 OCR 测试用小票图片（Owner: C）

为什么要有这个脚本：
    测试图如果只有几张、还全靠手工截图，换台电脑就没了，评审也没法复现。
    用代码画出来，任何人 clone 下来跑一遍就有图、有预期结果。

产出（默认写到 samples/receipts/）：
    sample_01_shaxian.png    沙县小吃  25.00 元  2026-11-20 12:30
    sample_02_starbucks.png  星巴克    36.00 元  2026-11-19 15:10
    sample_03_store.png      便利店    12.50 元  2026-11-18 08:05
    not_a_receipt.png        一张"风景照"，用来测"不是账单要报错"

⚠️ 这些是**合成图**，只保证"看起来像小票"，真实场景请再拍 1-2 张实物小票补充。
   合成图的好处是金额/时间完全可控，能当回归测试用（改了 prompt 跑一下就知道有没有退化）。

用法：
    python scripts/make_test_receipts.py
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "samples" / "receipts"

WIDTH, HEIGHT = 480, 720
MARGIN = 36

# Windows 自带的中文字体，按顺序找一个能用的
FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
)


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()   # 没中文字体时退化成英文，图还能出来


def _draw_receipt(merchant: str, lines: list[tuple[str, str]],
                  total: str, when: str, footer: str = "谢谢惠顾") -> Image.Image:
    """画一张小票：店名 + 分隔线 + 明细（左名右价）+ 合计 + 时间。"""
    img = Image.new("RGB", (WIDTH, HEIGHT), "white")
    d = ImageDraw.Draw(img)

    title_font = _font(34)
    body_font = _font(24)
    small_font = _font(20)

    d.rectangle([12, 12, WIDTH - 12, HEIGHT - 12], outline="black", width=2)
    d.text((WIDTH // 2, 70), merchant, font=title_font, fill="black", anchor="mm")
    d.text((WIDTH // 2, 112), "— 收 银 小 票 —", font=small_font, fill="gray", anchor="mm")

    d.line([MARGIN, 150, WIDTH - MARGIN, 150], fill="black", width=1)

    y = 180
    for name, price in lines:
        d.text((MARGIN, y), name, font=body_font, fill="black")
        d.text((WIDTH - MARGIN, y), price, font=body_font, fill="black", anchor="ra")
        y += 44

    y += 10
    d.line([MARGIN, y, WIDTH - MARGIN, y], fill="black", width=1)
    y += 24
    d.text((MARGIN, y), "合计", font=_font(30), fill="black")
    d.text((WIDTH - MARGIN, y), total, font=_font(30), fill="black", anchor="ra")

    y += 80
    d.text((MARGIN, y), f"时间：{when}", font=small_font, fill="black")
    y += 34
    d.text((MARGIN, y), "支付方式：微信支付", font=small_font, fill="black")
    y += 34
    d.text((MARGIN, y), f"单号：2026112{len(merchant) % 10}0001", font=small_font, fill="gray")

    d.text((WIDTH // 2, HEIGHT - 60), footer, font=small_font, fill="gray", anchor="mm")
    return img


def _draw_not_a_receipt() -> Image.Image:
    """一张"风景照"：天空渐变 + 太阳 + 山。用来测"不是小票要报错"。"""
    img = Image.new("RGB", (WIDTH, HEIGHT), "#87CEEB")
    d = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        d.line([(0, y), (WIDTH, y)],
               fill=(int(135 - 60 * ratio), int(206 - 80 * ratio), int(235 - 40 * ratio)))
    d.ellipse([330, 90, 410, 170], fill="#FFD966")
    d.polygon([(0, 520), (150, 360), (300, 520)], fill="#5B7F5B")
    d.polygon([(180, 540), (360, 330), (WIDTH, 540)], fill="#4A6B4A")
    d.rectangle([0, 540, WIDTH, HEIGHT], fill="#3E5C3E")
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    receipts = {
        "sample_01_shaxian.png": dict(
            merchant="沙县小吃",
            lines=[("拌面", "12.00"), ("蒸饺", "13.00")],
            total="25.00",
            when="2026-11-20 12:30",
        ),
        "sample_02_starbucks.png": dict(
            merchant="星巴克",
            lines=[("拿铁（大杯）", "33.00"), ("可颂", "3.00")],
            total="36.00",
            when="2026-11-19 15:10",
            footer="Thank you",
        ),
        "sample_03_store.png": dict(
            merchant="7-ELEVEN 便利店",
            lines=[("三明治", "7.50"), ("牛奶", "5.00")],
            total="12.50",
            when="2026-11-18 08:05",
        ),
    }

    for name, spec in receipts.items():
        _draw_receipt(**spec).save(OUT_DIR / name)
        print(f"已生成 {OUT_DIR / name}")

    _draw_not_a_receipt().save(OUT_DIR / "not_a_receipt.png")
    print(f"已生成 {OUT_DIR / 'not_a_receipt.png'}")

    expected = {
        "sample_01_shaxian.png": {
            "amount": 25.0, "merchant": "沙县小吃", "category": "餐饮",
            "occurred_at": "2026-11-20 12:30:00",
        },
        "sample_02_starbucks.png": {
            "amount": 36.0, "merchant": "星巴克", "category": "餐饮",
            "occurred_at": "2026-11-19 15:10:00",
        },
        "sample_03_store.png": {
            "amount": 12.5, "merchant": "7-ELEVEN 便利店", "category": "餐饮",
            "occurred_at": "2026-11-18 08:05:00",
        },
        "not_a_receipt.png": {"expect_error": True},
    }
    (OUT_DIR / "expected.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"已写入预期结果：{OUT_DIR / 'expected.json'}")


if __name__ == "__main__":
    main()
