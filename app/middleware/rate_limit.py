import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.redis import get_redis

# NFR-S08: auth endpoints 10/min per IP, general API 100/min per user
AUTH_RATE_LIMIT = 10
AUTH_WINDOW_SECONDS = 60
GENERAL_RATE_LIMIT = 100
GENERAL_WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            redis = await get_redis()
        except RuntimeError:
            # Redis not initialized (e.g., during tests)
            return await call_next(request)

        path = request.url.path

        if "/auth/" in path:
            key = f"ratelimit:auth:{request.client.host}"
            limit = AUTH_RATE_LIMIT
            window = AUTH_WINDOW_SECONDS
        elif path.startswith("/api/"):
            # Use Authorization header (JWT sub) if available, else IP
            auth_header = request.headers.get("authorization", "")
            identifier = auth_header[-16:] if auth_header else request.client.host
            key = f"ratelimit:api:{identifier}"
            limit = GENERAL_RATE_LIMIT
            window = GENERAL_WINDOW_SECONDS
        else:
            return await call_next(request)

        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, window)

        if current > limit:
            ttl = await redis.ttl(key)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": str(ttl)},
            )

        response = await call_next(request)
        return response
