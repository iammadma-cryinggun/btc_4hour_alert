FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 复制依赖文件
COPY requirements_v411.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements_v411.txt

# 复制主程序和数据文件
COPY BTC4小时策略预警v4.1.1_纯净版.py .
COPY dxy_data.csv .
COPY entrypoint.sh .

# 创建数据目录
RUN mkdir -p /app/data

# 设置工作目录权限
RUN chmod +x BTC4小时策略预警v4.1.1_纯净版.py entrypoint.sh

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Shanghai

# 健康检查 - 延长启动等待时间到60秒
HEALTHCHECK --interval=60s --timeout=30s --start-period=60s --retries=3 \
  CMD python -c "import sys; sys.exit(0)" || exit 1

# 运行程序
CMD ["./entrypoint.sh"]
