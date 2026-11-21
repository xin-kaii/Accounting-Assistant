# 个人记账与消费分析 AI 助手

> 2026 GDUF 人工智能工作室二轮考核 · 方向一 · 选题 A
> 队伍：**A / B / C / D** 4 人 · 零基础 · Python · 15 天

**一句话**：用人话记账、拍照记账、用一句话查账，超预算了提醒你。

---

## 一、目录结构

> 代码按**功能**分文件夹，不按人分。每个人维护哪些文件夹见 [`docs/分工与排期.md`](docs/分工与排期.md)。
> 要动别人维护的文件，先在群里说一声。

```
accounting-assistant/
├── app/                     应用代码
│   ├── config.py            配置（从 .env 读）
│   ├── constants.py         10 个分类、告警阈值
│   ├── api.py               REST 接口（可选加分项）
│   ├── db/                  建表 SQL、数据库连接
│   ├── services/            账单存取、统计、预算判断
│   ├── llm/                 模型调用、prompt、解析、离线兜底
│   ├── ocr/                 小票 / 截图识别
│   └── ui/                  5 个页面
│       └── main.py          Streamlit 入口
├── scripts/                 工具脚本（生成示例数据）
├── tests/                   单元测试
├── docs/                    分工排期、参考项目、数据契约、问题记录
├── data/                    运行时数据库（不提交）
├── assets/                  截图、架构图（README 里要显示）
├── samples/receipts/        测试用的小票图片
├── requirements.txt         依赖清单（版本已锁定）
├── requirements.lock.txt    完整版本快照（装完后生成）
├── Dockerfile               容器化
├── docker-compose.yml       Docker 一键启动
├── run.bat / run.sh         本地一键启动
├── .env.example             环境变量模板（复制成 .env 后填 Key）
└── README.md                本文件
```

| 模块 | 主要维护人 | 放什么 |
|---|---|---|
| `app/db/` `app/services/` | A | 建表、账单增删改查、统计、预算判断 |
| `app/llm/` | B | 调模型、3 个 prompt、3 个解析函数、离线兜底 |
| `app/ocr/` | C | 小票 / 支付截图识别 |
| `app/ui/` | D | 5 个页面的布局与交互 |
| `app/config.py` `app/constants.py` `app/api.py` `Dockerfile` | A | 配置、常量、接口、容器化 |
| `scripts/` | C | 生成示例数据 |
| `tests/` | 各模块作者 | 文件名前缀写模块名，见 `tests/README.md` |
| `docs/` | 全员 | 文档 |

---

## 二、5 个页面怎么分（D 搭界面，A/B 给数据）

| 页面 | 界面（D） | 数据对接（A / B） |
|---|---|---|
| `page_record.py` 记账页 | 输入框、确认卡片的位置、按钮 | **B**：卡片里显示什么、缺字段时提示什么 |
| `page_bills.py` 账单列表 | 表格、筛选器、按天分组 | D 自己（调 A 的 `list_transactions`） |
| `page_stats.py` 统计页 | 饼图放哪、折线图放哪、怎么切换 | **A**：`get_stats()` 的数据怎么变成图表 |
| `page_budget.py` 预算页 | 进度条、颜色、告警区 | **A**：`check_budget()` 的告警等级怎么显示 |
| `page_chat.py` 对话页 | 消息气泡、输入框、历史记录 | **B**：`parse_query()` 的结果怎么呈现 |

---

## 三、快速开始

### 1. 装环境（第 1 天做一次）

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

> **国内网络装依赖慢的话**，可以先换镜像源（可选，不是必须的）：
> ```bash
> pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
> ```

装完后留一条完整版本快照，方便队友和你装出完全一样的环境：

```bash
pip freeze > requirements.lock.txt
```

### 2. 配密钥

```bash
copy .env.example .env      # Windows
cp .env.example .env        # macOS / Linux
```

然后编辑 `.env`，填两家 API Key（文本模型 + 视觉模型）。

> ⚠️ **`.env` 绝对不能提交。** 它已经在 `.gitignore` 里了，别 `git add -f`。

### 3. 初始化数据库 + 示例数据

```bash
python -c "from app.db.conn import init_db; init_db()"
python scripts/generate_sample_data.py
```

### 4. 启动

```bash
streamlit run app/ui/main.py
```

或者直接双击 `run.bat`（Windows）/ 运行 `bash run.sh`（macOS、Linux）。

浏览器打开 http://localhost:8501

### 5. Docker（第 5 天后可用）

```bash
docker compose up -d --build
```

或者手动：

```bash
docker build -t booking-ai .
docker run -p 8501:8501 --env-file .env -v "%cd%/data:/app/data" booking-ai
```

---

## 四、团队分工

详见 [`docs/分工与排期.md`](docs/分工与排期.md)。参考资料见 [`docs/参考项目.md`](docs/参考项目.md)。

## 五、当前进度

- [ ] 第 1-2 天：环境验证 + 数据契约定稿
- [ ] 第 3-6 天：打通「输入一句话 → 确认 → 入库 → 列表可见」
- [ ] 第 7-10 天：图片识别、统计、查账、预算
- [ ] 第 11-13 天：Docker、测试、文档
- [ ] 第 14-16 天：冻结、彩排、提交

## 六、已知问题与未完成部分

> 第 13 天由 D 统稿填写。
