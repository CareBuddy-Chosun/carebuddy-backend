"""Refresh-token blocklist backed by Redis (used by logout / refresh).

Tokens are stored by SHA-256 hash with a TTL equal to the token's remaining
lifetime, so entries expire on their own. Redis failures fail-open (treat as
not-blocked) so a Redis outage never blocks legitimate refreshes — logout is a
best-effort revocation, not a hard security boundary.
"""

import hashlib

from redis.asyncio import Redis

from app.core.config import settings

_redis: Redis | None = None


def _client() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def _key(token: str) -> str:
    return "blocklist:" + hashlib.sha256(token.encode()).hexdigest()


async def block_token(token: str, ttl_seconds: int) -> None:
    """Add a token to the blocklist for ttl_seconds (minimum 1s)."""
    try:
        await _client().set(_key(token), "1", ex=max(1, ttl_seconds))
    except Exception:  # noqa: BLE001 — best-effort revocation
        pass


async def is_blocked(token: str) -> bool:
    """Return True if the token was revoked. Fail-open on Redis errors."""
    try:
        return await _client().exists(_key(token)) == 1
    except Exception:  # noqa: BLE001
        return False
