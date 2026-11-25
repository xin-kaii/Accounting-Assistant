# OCR 测试图

这些图是 `scripts/make_test_receipts.py` **用代码画出来的合成小票**，不是真实照片。
好处是金额、时间、商户完全可控，能当回归测试用；坏处是版式比真实小票干净得多。

| 文件 | 内容 | 预期识别结果 |
|---|---|---|
| `real_01.jpg` | **真·外卖订单截图**（老干妈火腿蛋炒饭，总价 15.9 / 实付 13.40） | 金额取 **13.40**（实付），餐饮，炒饭专家。文件里有"实付"字样时，程序会用正则覆盖模型取的总价 |
| `sample_01_shaxian.png` | 沙县小吃，拌面 12 + 蒸饺 13 | 合计 25.00，餐饮，2026-11-20 12:30 |
| `sample_02_starbucks.png` | 星巴克，拿铁 33 + 可颂 3 | 合计 36.00，餐饮，2026-11-19 15:10 |
| `sample_03_store.png` | 便利店，三明治 7.50 + 牛奶 5.00 | 合计 12.50，餐饮，2026-11-18 08:05 |
| `not_a_receipt.png` | 一张"风景照" | **必须报错**"没看出这是账单" |

`expected.json` 是机器可读的预期结果，测试时按它断言（金额精确、类别精确、商户做包含匹配）。

## 重新生成

```bash
python scripts/make_test_receipts.py
```

## 真实小票怎么补

合成图只能证明"流程通了"，证明不了"真实场景能用"。**至少再拍 1-2 张真小票/支付截图**：

- 文件名：`real_01_xxx.jpg`、`real_02_xxx.jpg`
- 拍照要求：别裁掉时间和合计，别反光过曝
- 拍完把实际金额/时间手工记到 `expected.json` 里

## 怎么手动试一次识别

`.env` 里的 `VLM_API_KEY` 还是占位符时，这一步会报"Key 还没填好"（这是预期行为，不会崩）。
换成真实 Key 之后：

```bash
python -c "from pathlib import Path; from app.ocr.receipt import extract_receipt; print(extract_receipt(Path('samples/receipts/sample_01_shaxian.png').read_bytes(), 'image/png'))"
```

盯着三个数：**耗时**、**金额对不对**、**confidence 多少**——这三个数就是答辩要说的"一张图多少钱、多少秒、准不准"。
