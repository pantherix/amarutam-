import json
import redis.asyncio as aioredis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from src.app.config import settings
import structlog

logger = structlog.get_logger()

class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_url: str):
        super().__init__(app)
        self.redis_url = redis_url

    async def dispatch(self, request: Request, call_next):
        # We only apply idempotency to write operations
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        # Resolve Redis client, falling back gracefully if offline
        redis_client = getattr(request.app.state, "redis", None)
        if redis_client is None:
            try:
                redis_client = aioredis.from_url(self.redis_url, decode_responses=True)
                await redis_client.ping()
                request.app.state.redis = redis_client
            except Exception:
                logger.warning("redis_offline_skipping_idempotency", url=self.redis_url)
                return await call_next(request)

        redis_key = f"idempotency:{idempotency_key}"
        try:
            cached_status = await redis_client.get(redis_key)
        except Exception:
            logger.warning("redis_query_failed_skipping_idempotency")
            return await call_next(request)

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
        try:
            await redis_client.setex(redis_key, 300, "processing")
        except Exception:
            pass

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
                try:
                    await redis_client.setex(redis_key, 86400, json.dumps(cache_payload))
                except Exception:
                    pass

            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
        except Exception as e:
            # Delete key on exception to allow retry
            try:
                await redis_client.delete(redis_key)
            except Exception:
                pass
            raise e
