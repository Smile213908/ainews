#!/usr/bin/env bash
# 开发依赖一键拉起：PostgreSQL 16 + Redis 7（docker compose）
# 已在运行会自动跳过；首次运行自动创建 pgdata / redisdata 卷。
# 用法：  bash scripts/dev-deps.sh
#        停止：docker compose stop db redis
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose up -d db redis

echo "等待 PostgreSQL / Redis 就绪…"
deadline=$((SECONDS + 60))
while [ $SECONDS -lt $deadline ]; do
  if docker compose exec -T db pg_isready -U hotmonitor >/dev/null 2>&1 \
     && docker compose exec -T redis redis-cli ping >/dev/null 2>&1; then
    echo "依赖就绪：PG localhost:5432 / Redis localhost:6379（端口以 .env 的 DB_PORT / REDIS_PORT 为准）"
    exit 0
  fi
  sleep 2
done
echo "等待超时，请执行 docker compose ps 查看状态" >&2
exit 1
