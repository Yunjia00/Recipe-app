[中文](README.md) | [English](README.en.md)

# My Recipes

A lightweight recipe app designed for everyday home cooking. It brings recipes, ingredient tracking, and “what do I already have at home?” into one interface so it is easier to decide what to cook.

The project uses FastAPI + SQLite with a static single-page HTML frontend. It works well for personal deployment and also serves as a small full-stack learning project.

![App screenshot](documents/screenshots.png)

## Features

- Browse, search, and filter recipes
- View recipes by cooking method
- Mark owned ingredients and match recipes automatically
- Create, edit, and delete recipes
- Manage ingredients, categories, and extra categories

## Tech Stack

- FastAPI
- SQLite
- Vanilla HTML / CSS / JavaScript
- Docker / Docker Compose

## Quick Start

Requirement: Python 3.12+

Using uv:

```bash
uv sync
uv run uvicorn server.main:app --reload --host 0.0.0.0 --port 3000
```

Then open: <http://localhost:3000>

## Project Structure

```text
.
├── documents/           # Screenshots and extra docs
├── public/              # Static frontend
├── server/              # FastAPI backend
├── data/                # SQLite database files
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Deployment

For deployment steps, environment variables, and Docker notes, see [documents/DEPLOYMENT.en.md](documents/DEPLOYMENT.en.md).

## Data

- The default database file is data/recipes.db
- Default seed data is imported from server/defaults.json on first startup
- Edit operations are protected by a password sent in the request header
