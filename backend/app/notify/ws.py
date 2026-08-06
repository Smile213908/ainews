"""WebSocket 连接管理（技术选型 §5.4）。

协议信封：{"event": "hotspot:new|notification|task:update", "data": {...}}
按关键词房间定向推送 + 全局广播（R-301）。单实例直接扇出；多实例经 Redis Pub/Sub。
"""

import json

import structlog
from fastapi import WebSocket

log = structlog.get_logger()


class ConnectionManager:
    def __init__(self) -> None:
        self._global: set[WebSocket] = set()
        self._rooms: dict[str, set[WebSocket]] = {}

    def connect(self, ws: WebSocket, keywords: list[str]) -> None:
        self._global.add(ws)
        for kw in keywords:
            self._rooms.setdefault(kw, set()).add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._global.discard(ws)
        for members in self._rooms.values():
            members.discard(ws)

    async def broadcast(self, event: str, data: dict, keyword: str | None = None) -> None:
        """keyword 为 None 时全局广播，否则定向推送到该关键词房间 + 全局连接。"""
        message = json.dumps({"event": event, "data": data}, ensure_ascii=False, default=str)
        targets = set(self._global)
        if keyword:
            targets |= self._rooms.get(keyword, set())
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()
