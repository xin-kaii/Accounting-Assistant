"""全局常量（Owner: A）

分类体系写死在这里，不做成可配置——零基础团队没有精力维护动态分类。
答辩时如果被问"为什么不做可配置分类"，答：先保证 4 项功能跑通，可配置是下一版的事。
"""

# 10 个固定分类。新增/修改都要先在群里说，因为 B 的 prompt、页面的图表、C 的识别都依赖它。
CATEGORIES: tuple[str, ...] = (
    "餐饮",
    "交通",
    "购物",
    "娱乐",
    "居住",
    "医疗",
    "教育",
    "通讯",
    "人情",
    "其他",
)

# 兜底分类：模型认不出来时用它，永远不返回空字符串
DEFAULT_CATEGORY = "其他"

# 收支方向
DIRECTION_EXPENSE = "expense"
DIRECTION_INCOME = "income"
DIRECTIONS = (DIRECTION_EXPENSE, DIRECTION_INCOME)

# 数据来源（一条账是怎么进来的），体现在账单表的 source 字段
SOURCE_TEXT = "text"        # 用户打的一句话
SOURCE_RECEIPT = "receipt"  # 拍照/截图识别
SOURCE_MANUAL = "manual"    # 页面上的表单手动填
SOURCES = (SOURCE_TEXT, SOURCE_RECEIPT, SOURCE_MANUAL)

# 预算告警等级：A 的 check_budget() 返回这三档，页面据此上色
LEVEL_OK = "ok"      # < 70%
LEVEL_WARN = "warn"  # 70% ~ 100%
LEVEL_OVER = "over"  # > 100%

# 告警阈值（百分比）
BUDGET_WARN_RATIO = 0.70
BUDGET_OVER_RATIO = 1.00
