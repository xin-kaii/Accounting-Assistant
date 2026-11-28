# A 负责。第 5 天：能 build + run；第 11 天完善：非 root、健康检查、时区、镜像体积。
# 用法：docker compose up -d --build
#
# 3.13 对齐本地实测环境：requirements.lock.txt 是在 Python 3.13.9 上生成的，
# 镜像里的 Python 版本要和"测过的组合"一致，不然等于跑一个没验证过的环境。
# 基础镜像版本做成可覆盖的（ARG 必须放在 FROM 之前）：
#   默认   docker compose build                          -> python:3.13-slim
#   离线   docker build --build-arg PYTHON_TAG=3.11 .    -> 用本地缓存的 3.11（国内拉不动 docker.io 时的退路）
ARG PYTHON_TAG=3.13
FROM python:${PYTHON_TAG}-slim

# ---------- 运行时环境 ----------
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# ---------- pip 源：国内构建快；评审想用官方源就加参数 ----------
# docker compose build --build-arg PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip config set global.index-url "$PIP_INDEX_URL"

# ---------- 先装依赖再拷代码：改代码时不用重装（Docker 层缓存）----------
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------- 非 root 用户：root 跑容器是安全扣分项 ----------
RUN useradd --create-home --uid 1000 appuser
COPY --chown=appuser:appuser . .
USER appuser

# 数据库放这里，挂 volume 才能持久化（容器删了，账单还在）
VOLUME ["/app/data"]
EXPOSE 8501

# ---------- 健康检查：slim 里没有 curl，用 python 自带的 urllib，省一个依赖 ----------
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health').read().strip()==b'ok' else 1)"

# --server.address=0.0.0.0 必须：否则容器外访问不到
CMD ["streamlit", "run", "app/ui/main.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501"]
