import json
import redis.asyncio as aioredis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from src.app.config import settings

class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_url: str):
        super().__init__(app)
        self.redis_url = redis_url

    async def dispatch(self, request: Request, call_next):
        # Resolve Redis client from application state first, supporting testing injections
        redis_client = getattr(request.app.state, "redis", None)
        if redis_client is None:
            redis_client = aioredis.from_url(self.redis_url, decode_responses=True)
            request.app.state.redis = redis_client

        # We only apply idempotency to write operations
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        redis_key = f"idempotency:{idempotency_key}"
        cached_status = await redis_client.get(redis_key)

        if cached_status == "processing":
            return Response(
                content=json.dumps({"detail": "An identical request is already being processed."}),
                status_code=409,
                media_type="application/json"
            )
        elif cached_status:
            # Request completed, return cached response
            cached_res = json.loads(cached_status)
            return Response(
                content=cached_res["body"],
                status_code=cached_res["status_code"],
                headers=cached_res["headers"],
                media_type="application/json"
            )

        # Set to processing in Redis
        await redis_client.setex(redis_key, 300, "processing")

        try:
            response = await call_next(request)
            
            # If the response is a streaming response, we consume and cache it.
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            if response.status_code < 500:
                cache_payload = {
                    "status_code": response.status_code,
                    "body": response_body.decode("utf-8"),
                    "headers": {k: v for k, v in response.headers.items() if k.lower() not in ("content-length",)}
                }
                # Cache response for 24 hours
                await redis_client.setex(redis_key, 86400, json.dumps(cache_payload))

            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
        except Exception as e:
            # Delete key on exception to allow retry
            await redis_client.delete(redis_key)
            raise e
