"""FastAPI 应用入口。

本地开发：uv run fastapi dev app/main.py
生产：granian --interface asgi app.main:app
"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  确保表模型注册
from app.config import get_settings
from app.core.redis import close_redis
from app.core.scheduler import start_scheduler
from app.db import init_db
from app.deps import require_api_key
from app.notify.ws import ws_manager
from app.routers import control, hotspots, keywords, notifications, sources, system

log = structlog.get_logger()

# 启动即校验配置：缺失必填项（API_KEYS）在此直接抛错（PRD §6 安全要求）
get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()  # 开发便捷建表；生产由 Alembic 管理
    async with AsyncExitStack() as stack:
        await start_scheduler(stack)  # 30 分钟定时检查（R-101）
        yield
    await close_redis()


app = FastAPI(title="hot-monitor 2.0 API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:7100"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全部业务 API 走鉴权（FR-7.1）；仅 /api/health 与 /docs 开放（探针与契约调试）
for r in (keywords.router, hotspots.router, notifications.router, sources.router, control.router):
    app.include_router(r, prefix="/api", dependencies=[Depends(require_api_key)])
app.include_router(system.router, prefix="/api")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, api_key: str = "", keywords: str = ""):
    """WS 握手校验 API Key（FR-7.1）：/ws?api_key=xxx&keywords=a,b"""
    settings = get_settings()
    if api_key not in settings.api_key_list:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    rooms = [k.strip() for k in keywords.split(",") if k.strip()]
    ws_manager.connect(websocket, rooms)
    try:
        while True:
            # 客户端上行目前仅用于心跳/订阅变更，内容忽略
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(websocket)
