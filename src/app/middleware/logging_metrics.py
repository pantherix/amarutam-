import os
import time
import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram

# Initialize structlog configuration
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Prometheus Metrics
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP Requests",
    ["method", "endpoint", "status"]
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP Request Latency in seconds",
    ["method", "endpoint"]
)

class LoggingMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        method = request.method
        path = request.url.path
        
        # Correlation ID injection
        correlation_id = request.headers.get("X-Correlation-ID", os.urandom(8).hex())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            status_code = 500
            logger.exception("request_failed", path=path, method=method, error=str(e))
            raise e
        finally:
            duration = time.perf_counter() - start_time
            # Increment Prometheus counters
            HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=path, status=status_code).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=path).observe(duration)
            
            logger.info(
                "request_completed",
                path=path,
                method=method,
                status_code=status_code,
                duration=f"{duration:.4f}s"
            )
