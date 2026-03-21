[中文](README.md) | [English](README.en.md)

# 喵王的食谱

一个面向家庭场景的轻量食谱应用：把菜谱、食材库存、到期管理和 AI 做饭建议整合在一个页面里。

后端使用 FastAPI + SQLite，前端是原生 HTML/CSS/JS 单页应用，适合个人部署和小型家庭共享。

![应用截图](documents/screenshots.png)

## 当前功能

- 菜谱管理：新增、编辑、删除、搜索、按烹饪方式筛选
- 食材管理：按分类维护食材，勾选是否拥有，支持入库日期/过期日期
- 过期处理：一键清理已过期且已拥有的食材状态
- 多家庭（House）隔离：不同家庭拥有独立食材与分类
- AI 智能推荐：
 	- 基于已选食材生成推荐
 	- 支持模型切换：`mistral-large-latest` / `mistral-medium-latest` / `mistral-small-latest`
 	- 结果按 Markdown 渲染
 	- 带请求耗时计时器

## 技术栈

- FastAPI
- SQLite
- 原生 HTML / CSS / JavaScript
- OpenAI 兼容 SDK（当前可接 Mistral API）
- Docker / Docker Compose

## 本地开发

要求：Python 3.12+

1. 安装依赖

```bash
uv sync
```

1. 配置环境变量（推荐放在 `server/.env`）

```dotenv
PORT=3001
RECIPE_PASSWORD=your-password

LLM_API_URL=https://api.mistral.ai/v1
LLM_API_KEY=your-api-key
LLM_MODEL=mistral-large-latest
LLM_TIMEOUT_SECONDS=20
```

1. 启动服务（建议在 `server/` 目录）

```bash
cd server
uv run uvicorn main:app --reload --log-level debug
```

1. 打开浏览器访问

- 如果你用命令行显式指定端口，就访问对应端口
- 如果使用 `.env` 里的 `PORT=3001`，则访问 <http://localhost:3001>

## 环境变量

- `PORT`：服务端口
- `RECIPE_PASSWORD`：写操作密码（通过请求头 `x-recipe-password` 验证）
- `DB_PATH`：SQLite 文件路径（未设置时默认 `data/recipes.db`）
- `LLM_API_URL`：OpenAI 兼容 API Base URL（Mistral 可用 `https://api.mistral.ai/v1`）
- `LLM_API_KEY`：LLM Key
- `LLM_MODEL`：默认模型（当请求未指定时使用）
- `LLM_TIMEOUT_SECONDS`：LLM 请求超时秒数

## Docker 运行

```bash
docker compose up --build -d
```

注意：当前 `docker-compose.yml` 使用了外部网络 `homelab`。如果本机没有该网络，请先创建或按需修改 compose 配置。

## 项目结构

```text
.
├── data/                # SQLite 数据文件
├── documents/           # 部署文档与截图
├── public/              # 前端静态页面
├── server/              # FastAPI 后端
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── README.md
└── README.en.md
```

## 部署文档

- 中文部署说明： [documents/DEPLOYMENT.md](documents/DEPLOYMENT.md)
- English deployment guide: [documents/DEPLOYMENT.en.md](documents/DEPLOYMENT.en.md)
