# A 负责。第 5 天先写第一版（能 build + run 就行），第 11 天再完善
# 第一版只需要这几行；第 11 天要加的：非 root 用户、健康检查、更小的镜像
FROM python:3.11-slim

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
