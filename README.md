# 我的食谱 — 部署说明

## 文件结构

```
recipe-app/
├── docker-compose.yml     ← 启动配置
├── Dockerfile
├── data/                  ← 数据库自动生成在这里（自动创建）
├── public/
│   └── index.html         ← 前端页面
└── server/
    ├── index.js           ← 后端服务
    ├── package.json
    └── defaults.json      ← 预设菜谱和食材数据
```

---

## 部署步骤

### 1. 安装 Docker（如果还没装）

```bash
curl -fsSL https://get.docker.com | sh
```

### 2. 把整个 recipe-app 文件夹传到服务器

可以用 scp：
```bash
scp -r recipe-app/ 你的用户名@服务器IP:/home/你的用户名/
```

### 3. 在服务器上启动

```bash
cd recipe-app
docker compose up -d
```

就这样！访问 `http://服务器IP:3000` 即可使用。

---

## 常用命令

```bash
# 查看运行状态
docker compose ps

# 查看日志
docker compose logs -f

# 停止
docker compose down

# 更新代码后重新构建
docker compose up -d --build
```

---

## 数据备份

所有数据存在 `./data/recipes.db`（SQLite 文件）。

备份只需复制这个文件：
```bash
cp data/recipes.db data/recipes_backup_$(date +%Y%m%d).db
```

恢复：替换 `data/recipes.db` 后重启容器即可。

---

## 修改端口

编辑 `docker-compose.yml`，把 `"3000:3000"` 左边的数字改成你想要的端口：

```yaml
ports:
  - "8080:3000"   # 改成通过 8080 访问
```

然后重启：`docker compose up -d`
