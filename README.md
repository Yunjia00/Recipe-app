[中文](README.md) | [English](README.en.md)

# 我的食谱

一个为家庭日常使用设计的轻量食谱应用。它把菜谱、食材清单和“我现在家里有什么”这三件事放到同一个界面里，方便快速决定今天做什么。

项目采用 FastAPI + SQLite，前端为单页静态 HTML，适合个人部署，也适合作为简单的全栈练习项目。

![应用截图](documents/screenshots.png)

## 功能

- 浏览、搜索和筛选菜谱
- 按烹饪方式查看菜谱
- 勾选当前已有食材，自动匹配可做的菜
- 新增、编辑、删除菜谱
- 管理食材、分类和额外分类

## 技术栈

- FastAPI
- SQLite
- 原生 HTML / CSS / JavaScript
- Docker / Docker Compose

## 快速开始

要求：Python 3.12+

使用 uv：

```bash
uv sync
uv run uvicorn server.main:app --reload --host 0.0.0.0 --port 3000
```

启动后访问：<http://localhost:3000>

## 项目结构

```text
.
├── documents/           # 截图与补充文档
├── public/              # 前端静态页面
├── server/              # FastAPI 后端
├── data/                # SQLite 数据文件
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## 部署

部署方式、环境变量、Docker 注意事项见 [documents/DEPLOYMENT.md](documents/DEPLOYMENT.md)。

## 数据

- 默认数据库文件是 data/recipes.db
- 首次启动时会导入 server/defaults.json 中的预设数据
- 编辑操作通过请求头中的密码保护
