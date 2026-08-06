"""Redis 客户端（技术选型 §5.2）：锁 / AI 缓存 / 扩展缓存 / 广播通道。

本地无 Redis 时自动降级为进程内实现（仅单进程开发可用），生产必须配置 Redis。
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog

from app.config import get_settings

log = structlog.get_logger()

_redis: Any = None
_redis_checked = False

# ---- 进程内降级实现 ----
_memory_cache: dict[str, tuple[Any, float | None]] = {}
_memory_locks: dict[str, float] = {}


async def get_redis():
    """返回可用的 redis.asyncio 客户端；不可用时返回 None（走降级路径）。"""
    global _redis, _redis_checked
    if _redis_checked:
        return _redis
    _redis_checked = True
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(
            get_settings().redis_url, socket_connect_timeout=2, decode_responses=True
        )
        await client.ping()
        _redis = client
        log.info("redis_connected", url=get_settings().redis_url)
    except Exception as e:
        _redis = None
        log.warning("redis_unavailable_fallback_memory", error=str(e))
    return _redis


# ---------- 缓存（AI 结果 / 查询扩展） ----------
async def cache_get(key: str) -> Any | None:
    r = await get_redis()
    if r is not None:
        raw = await r.get(key)
        return json.loads(raw) if raw else None
    entry = _memory_cache.get(key)
    if not entry:
        return None
    value, expires_at = entry
    if expires_at and time.time() > expires_at:
        _memory_cache.pop(key, None)
        return None
    return value


async def cache_set(key: str, value: Any, ttl_seconds: int) -> None:
    r = await get_redis()
    if r is not None:
        await r.set(key, json.dumps(value, ensure_ascii=False), ex=ttl_seconds)
        return
    _memory_cache[key] = (value, time.time() + ttl_seconds)


# ---------- 分布式锁 ----------
async def acquire_lock(name: str, ttl_seconds: int, token: str) -> bool:
    """SET NX EX 语义；Redis 不可用时用进程内锁（单进程开发等价）。"""
    r = await get_redis()
    if r is not None:
        return bool(await r.set(f"lock:{name}", token, nx=True, ex=ttl_seconds))
    expires = _memory_locks.get(name)
    if expires and time.time() < expires:
        return False
    _memory_locks[name] = time.time() + ttl_seconds
    return True


async def renew_lock(name: str, ttl_seconds: int, token: str) -> None:
    r = await get_redis()
    if r is not None:
        # 仅当持锁人是自己时续期（看门狗）
        await r.eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('expire', KEYS[1], ARGV[2]) else return 0 end",
            1,
            f"lock:{name}",
            token,
            ttl_seconds,
        )
        return
    if name in _memory_locks:
        _memory_locks[name] = time.time() + ttl_seconds


async def release_lock(name: str, token: str) -> None:
    r = await get_redis()
    if r is not None:
        await r.eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) else return 0 end",
            1,
            f"lock:{name}",
            token,
        )
        return
    _memory_locks.pop(name, None)


# ---------- Pub/Sub（WS 广播） ----------
async def publish(channel: str, message: dict) -> None:
    r = await get_redis()
    if r is not None:
        await r.publish(channel, json.dumps(message, ensure_ascii=False, default=str))
    # 单进程时 WS 管理器直接扇出，无需本地 fallback


async def close_redis() -> None:
    global _redis, _redis_checked
    if _redis is not None:
        await _redis.aclose()
    _redis = None
    _redis_checked = False
