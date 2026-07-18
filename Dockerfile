# syntax=docker/dockerfile:1
# Multi-stage: build SPA, then run FastAPI + static dist.

FROM node:20-bookworm-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY --from=frontend /src/frontend/dist /app/frontend/dist
COPY config.yaml /app/config.yaml
RUN mkdir -p /app/data/logger

ENV PYTHONPATH=/app/backend
EXPOSE 8080

# Bind all interfaces inside the container (config.yaml host is ignored for listen).
# Runs as root so bind-mounted ./data and ./config.yaml stay writable for local compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
