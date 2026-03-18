FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN git config --global --add safe.directory /app
COPY pyproject.toml .
RUN pip install .
COPY server/ ./server/
COPY public/ ./public/
RUN mkdir -p /data
EXPOSE 3000
ENV DB_PATH=/data/recipes.db
ENV PORT=3000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000", "--app-dir", "/app/server"]
