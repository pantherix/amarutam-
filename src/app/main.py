from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
import redis.asyncio as aioredis
from sqlalchemy import text

from src.app.config import settings
from src.app.database import init_db, get_db
from src.app.middleware import IdempotencyMiddleware, LoggingMetricsMiddleware
from src.app.api.v1.auth import router as auth_router
from src.app.api.v1.doctors import router as doctors_router
from src.app.api.v1.bookings import router as bookings_router
from src.app.api.v1.admin import router as admin_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Middlewares
app.add_middleware(LoggingMetricsMiddleware)
app.add_middleware(IdempotencyMiddleware, redis_url=settings.REDIS_URL)

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

@app.on_event("startup")
async def startup_event():
    # Initialize database tables
    await init_db()

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check(db=Depends(get_db)):
    # Verify Database Connection
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database healthcheck failed: {str(e)}"
        )
        
    # Verify Redis Connection
    try:
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await client.ping()
        await client.close()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Redis healthcheck failed: {str(e)}"
        )
        
    return {"status": "healthy", "database": "connected", "redis": "connected"}

# Include API Routers
app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(doctors_router, prefix=f"{settings.API_V1_STR}/doctors", tags=["doctors"])
app.include_router(bookings_router, prefix=f"{settings.API_V1_STR}/bookings", tags=["bookings"])
app.include_router(admin_router, prefix=f"{settings.API_V1_STR}/admin", tags=["admin"])
