# 使用官方Python基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用文件
COPY . .

# 创建持久化数据目录
RUN mkdir /data

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "2"]
FROM python:3.10-slim
LABEL "language"="python"
LABEL "framework"="flask"
WORKDIR /src
COPY . .
RUN pip install --upgrade pip && pip install flask requests
EXPOSE 8080
CMD ["python", "app.py"]
