FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install .
COPY server/ ./server/
COPY public/ ./public/
RUN mkdir -p /data
EXPOSE 3000
ENV DB_PATH=/data/recipes.db
ENV PORT=3000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000", "--app-dir", "/app/server"]

# FROM node:20-alpine

# WORKDIR /app

# # 安装依赖
# COPY server/package.json ./
# RUN npm install --production

# # 复制服务器代码和前端
# COPY server/ ./
# COPY public/ ./public/

# # 数据目录（挂载卷用）
# RUN mkdir -p /data

# EXPOSE 3000

# ENV DB_PATH=/data/recipes.db
# ENV PORT=3000

# CMD ["node", "index.js"]
