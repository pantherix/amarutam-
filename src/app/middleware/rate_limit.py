import time
import redis.asyncio as aioredis
from fastapi import Request, HTTPException, status
from src.app.config import settings

class RateLimiter:
    def __init__(self, limit: int = 60, window: int = 60):
        """
        limit: Number of requests allowed
        window: Window size in seconds
        """
        self.limit = limit
        self.window = window
        self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    async def __call__(self, request: Request):
        # Identify user by client IP address
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        
        # Use simple fixed-window counter in Redis
        current_bucket = int(time.time()) // self.window
        redis_key = f"rate_limit:{client_ip}:{path}:{current_bucket}"
        
        count = await self.redis.get(redis_key)
        if count and int(count) >= self.limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down."
            )
            
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(redis_key)
            pipe.expire(redis_key, self.window)
            await pipe.execute()
