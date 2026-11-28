# A 负责。第 5 天先写第一版（能 build + run 就行），第 11 天再完善
# 第一版只需要这几行；第 11 天要加的：非 root 用户、健康检查、更小的镜像

# 3.13 对齐本地实测环境：requirements.lock.txt 是在 Python 3.13.9 上生成的，
# 镜像里的 Python 版本要和"测过的组合"一致，不然等于跑一个没验证过的环境。
# 基础镜像版本做成可覆盖的（ARG 必须放在 FROM 之前）：
#   默认   docker compose build                          -> python:3.13-slim
#   离线   docker build --build-arg PYTHON_TAG=3.11 .    -> 用本地缓存的 3.11（国内拉不动 docker.io 时的退路）
ARG PYTHON_TAG=3.13
FROM python:${PYTHON_TAG}-slim

# 不设时区容器里是 UTC，conn.now_str() 生成的 created_at 会比本地早 8 小时
ENV TZ=Asia/Shanghai

# 不写 .pyc、日志立刻输出
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 先装依赖，改代码时不用重装（利用 Docker 层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 数据库文件放这里，挂载 volume 才能持久化（容器删了数据还在）
VOLUME ["/app/data"]

EXPOSE 8501

CMD ["streamlit", "run", "app/ui/main.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true"]
