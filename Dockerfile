FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖（包括MySQL客户端库）
RUN apt-get update && apt-get install -y default-libmysqlclient-dev build-essential pkg-config && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY . .

# 直接使用requirements.txt安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建日志目录
RUN mkdir -p /app/logs

# 设置环境变量
ENV FLASK_APP=wsgi.py
ENV FLASK_ENV=production
ENV TZ=Asia/Shanghai

# 暴露端口
EXPOSE 8000

# 创建启动脚本 - 完全删除迁移相关步骤
RUN echo '#!/bin/bash\n\
echo "检查安装的包:"\n\
pip list | grep flask\n\
echo "启动应用..."\n\
exec gunicorn --bind 0.0.0.0:$PORT wsgi:app\n\
' > /app/start.sh && chmod +x /app/start.sh

# 启动应用
CMD ["/app/start.sh"]