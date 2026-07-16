# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.11.5
ARG NODE_VERSION=22

FROM node:${NODE_VERSION}-alpine AS frontend-builder
WORKDIR /frontend

COPY frontend-vue/package*.json ./
RUN npm ci

COPY frontend-vue ./
RUN npm run build

FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/appuser

WORKDIR /app

ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/home/appuser" \
    --shell "/bin/bash" \
    --uid "${UID}" \
    appuser

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser alembic.ini ./alembic.ini
COPY --chown=appuser:appuser config.py ./config.py
COPY --from=frontend-builder --chown=appuser:appuser /frontend/dist ./frontend-vue/dist

RUN mkdir -p /app/storage && chown -R appuser:appuser /app/storage

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
