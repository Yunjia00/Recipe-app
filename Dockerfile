FROM node:20-alpine

WORKDIR /app

# 安装依赖
COPY server/package.json ./
RUN npm install --production

# 复制服务器代码和前端
COPY server/ ./
COPY public/ ./public/

# 数据目录（挂载卷用）
RUN mkdir -p /data

EXPOSE 3000

ENV DB_PATH=/data/recipes.db
ENV PORT=3000

CMD ["node", "index.js"]
