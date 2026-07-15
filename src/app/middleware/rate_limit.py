import time
import redis.asyncio as aioredis
from fastapi import Request, HTTPException, status
from src.app.config import settings
import structlog

logger = structlog.get_logger()

class RateLimiter:
    def __init__(self, limit: int = 60, window: int = 60):
        """
        limit: Number of requests allowed
        window: Window size in seconds
        """
        self.limit = limit
        self.window = window
        self.redis_client = None

    async def __call__(self, request: Request):
        # Resolve Redis client, support test mock injection in app state
        redis_conn = getattr(request.app.state, "redis", None)
        
        if redis_conn is None:
            if self.redis_client is None:
                try:
                    self.redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
                    await self.redis_client.ping()
                except Exception:
                    # Redis is offline, bypass rate limiting gracefully in lite mode
                    logger.warning("redis_offline_skipping_rate_limiting", url=settings.REDIS_URL)
                    return
            redis_conn = self.redis_client

        # Identify user by client IP address
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        
        current_bucket = int(time.time()) // self.window
        redis_key = f"rate_limit:{client_ip}:{path}:{current_bucket}"
        
        try:
            count = await redis_conn.get(redis_key)
            if count and int(count) >= self.limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please slow down."
                )
                
            async with redis_conn.pipeline(transaction=True) as pipe:
                pipe.incr(redis_key)
                pipe.expire(redis_key, self.window)
                await pipe.execute()
        except HTTPException:
            raise
        except Exception as e:
            # Skip rate limiting gracefully on Redis query failure
            logger.warning("rate_limiting_failed_skipping", error=str(e))
            return
