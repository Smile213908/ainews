"""FastAPI 应用入口。

本地开发：uv run fastapi dev app/main.py
生产：granian --interface asgi app.main:app
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  确保表模型注册
from app.config import get_settings
from app.db import init_db
from app.deps import require_api_key
from app.routers import hotspots, keywords, notifications, sources, system

# 启动即校验配置：缺失必填项（API_KEYS）在此直接抛错（PRD §6 安全要求）
get_settings()

app = FastAPI(title="hot-monitor 2.0 API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:7100"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全部业务 API 走鉴权（FR-7.1）；仅 /api/health 与 /docs 开放（探针与契约调试）
for r in (keywords.router, hotspots.router, notifications.router, sources.router):
    app.include_router(r, prefix="/api", dependencies=[Depends(require_api_key)])
app.include_router(system.router, prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    init_db()  # 开发便捷建表；生产由 Alembic 管理
