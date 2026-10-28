"""Async Redis client storing JSON documents with optional TTLs.

Voice calls and inline appointment booking keep their state here so Twilio
webhooks (which are stateless HTTP requests) can resume a conversation.
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from app.shared.core.config import get_settings


class RedisJsonCache:
    """Thin async wrapper around Redis for JSON-serialisable values."""

    def __init__(self) -> None:
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Open the connection pool (idempotent at the driver level)."""
        self._client = aioredis.from_url(
            get_settings().redis_url,
            decode_responses=True,
        )

    async def disconnect(self) -> None:
        """Close the pool and release sockets."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def _redis(self) -> aioredis.Redis:
        if not self._client:
            raise RuntimeError("Redis cache is not connected; call connect() first.")
        return self._client

    async def get_json(self, key: str) -> dict[str, Any] | None:
        raw = await self._redis.get(key)
        return json.loads(raw) if raw else None

    async def set_json(
        self, key: str, value: dict[str, Any], ttl_seconds: int | None = None
    ) -> None:
        await self._redis.set(key, json.dumps(value), ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def scan_keys(self, pattern: str) -> list[str]:
        """List keys matching a glob, using SCAN so large keyspaces stay cheap."""
        return [key async for key in self._redis.scan_iter(match=pattern)]


cache = RedisJsonCache()
