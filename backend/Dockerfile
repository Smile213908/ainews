# hot-monitor 2.0 API（技术选型 §9.1）
FROM python:3.12-slim AS base

WORKDIR /app

# uv 安装依赖（uv.lock 锁定版本）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

EXPOSE 8000

# 生产用 Granian（技术选型 §4.2）；迁移由启动命令先执行
CMD ["sh", "-c", "uv run --no-sync alembic upgrade head && uv run --no-sync granian --interface asgi --host 0.0.0.0 --port 8000 app.main:app"]
