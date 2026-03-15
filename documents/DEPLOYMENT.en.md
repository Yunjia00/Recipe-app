[中文](DEPLOYMENT.md) | [English](DEPLOYMENT.en.md)

# Deployment Guide

This document covers the basic deployment options for this project in local, Docker, and server environments.

## Environment Variables

The project uses the following environment variables:

- RECIPE_PASSWORD: Password required for editing recipes and ingredients. The default value is changeme
- DB_PATH: SQLite database path. The default is data/recipes.db
- PORT: Service port. The default is 3000

For local development, you can create a .env file in the project root:

```env
RECIPE_PASSWORD=your-password
DB_PATH=./data/recipes.db
PORT=3000
```

## Run Locally

Requirement: Python 3.12+

Using uv:

```bash
uv sync
uv run uvicorn server.main:app --reload --host 0.0.0.0 --port 3000
```

Using pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install .
uvicorn server.main:app --reload --host 0.0.0.0 --port 3000
```

Then open: <http://localhost:3000>

## Docker Deployment

Build and start the container:

```bash
docker compose up -d --build
```

Check status and logs:

```bash
docker compose ps
docker compose logs -f
```

Stop the service:

```bash
docker compose down
```

## Data Persistence

- The database path inside the container is /data/recipes.db
- The compose file mounts the local data directory to /data in the container
- To back up the app, copy data/recipes.db directly

```bash
cp data/recipes.db data/recipes_backup_$(date +%Y%m%d).db
```

## Port Mapping

The default mapping is 3000:3000.

If you want to expose the app on port 8080 instead, update docker-compose.yml:

```yaml
ports:
  - "8080:3000"
```

Then rebuild and restart:

```bash
docker compose up -d --build
```

## External Network Note

The current docker-compose.yml uses an external network named homelab.

If the network does not exist on your host, create it first:

```bash
docker network create homelab
```

If you do not need this network, you can also remove the related networks section from docker-compose.yml.

## Production Notes

- Change the default password changeme as soon as possible
- Back up data/recipes.db regularly
- If the app is exposed to the public internet, place it behind a reverse proxy
- For home network use, the current Docker setup is usually sufficient
