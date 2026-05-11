from redis.asyncio import Redis


async def add_to_blocklist(redis: Redis, jti: str, ttl_seconds: int) -> None:
    """Add an access token JTI to the Redis blocklist."""
    await redis.setex(f"blocklist:{jti}", ttl_seconds, "1")


async def is_blocklisted(redis: Redis, jti: str) -> bool:
    """Check if an access token JTI has been blocklisted."""
    return await redis.exists(f"blocklist:{jti}") > 0
