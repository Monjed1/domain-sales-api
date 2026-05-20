from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Awaitable, Callable, TypeVar

from cachetools import TTLCache

from app.core.config import get_settings

T = TypeVar("T")


class CacheService:
    def __init__(self) -> None:
        settings = get_settings()
        self._cache: TTLCache[str, Any] = TTLCache(
            maxsize=512,
            ttl=settings.cache_ttl_seconds,
        )
        self._lock = threading.Lock()
        self._pending: dict[str, asyncio.Future[Any]] = {}

    async def get_or_set(self, key: str, factory: Callable[[], Awaitable[T]]) -> T:
        with self._lock:
            if key in self._cache:
                return self._cache[key]

        try:
            value = await factory()
        except Exception:
            with self._lock:
                self._pending.pop(key, None)
            raise

        with self._lock:
            self._cache[key] = value
            self._pending.pop(key, None)
            return value

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


cache_service = CacheService()


def cache_key(*parts: str) -> str:
    return ":".join(parts)


def stamp() -> str:
    return str(int(time.time()))
