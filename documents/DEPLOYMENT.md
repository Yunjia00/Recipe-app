[中文](DEPLOYMENT.md) | [English](DEPLOYMENT.en.md)

# 部署须知

本文档说明这个项目在本地、Docker 和服务器环境中的基本部署方式。

## 环境变量

项目使用以下环境变量：

- RECIPE_PASSWORD：编辑菜谱和食材时使用的密码，默认值是 changeme
- DB_PATH：SQLite 数据库路径，默认是 data/recipes.db
- PORT：服务监听端口，默认是 3000

本地可以在项目根目录创建 .env 文件：

```env
RECIPE_PASSWORD=your-password
DB_PATH=./data/recipes.db
PORT=3000
```

## 本地运行

要求：Python 3.12+

使用 uv：

```bash
uv sync
uv run uvicorn server.main:app --reload --host 0.0.0.0 --port 3000
```

使用 pip：

```bash
python -m venv .venv
source .venv/bin/activate
pip install .
uvicorn server.main:app --reload --host 0.0.0.0 --port 3000
```

启动后访问：<http://localhost:3000>

## Docker 部署

构建并启动：

```bash
docker compose up -d --build
```

查看状态和日志：

```bash
docker compose ps
docker compose logs -f
```

停止服务：

```bash
docker compose down
```

## 数据持久化

- 容器内数据库路径是 /data/recipes.db
- compose 已将本地 data 目录挂载到容器内 /data
- 备份时直接复制 data/recipes.db 即可

```bash
cp data/recipes.db data/recipes_backup_$(date +%Y%m%d).db
```

## 端口

默认映射是 3000:3000。

如果你想改为 8080 对外访问，可以修改 docker-compose.yml：

```yaml
ports:
  - "8080:3000"
```

修改后重新执行：

```bash
docker compose up -d --build
```

## 外部网络说明

当前 docker-compose.yml 配置了外部网络 homelab。

如果宿主机上还没有这个网络，可以先创建：

```bash
docker network create homelab
```

如果你不需要这个网络，也可以删除 docker-compose.yml 中对应的 networks 配置。

## 生产环境建议

- 尽快修改默认密码 changeme
- 定期备份 data/recipes.db
- 如果要暴露到公网，建议放在反向代理后面
- 如果是家庭内网使用，Docker 部署已经足够简单直接
