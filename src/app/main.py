import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from prometheus_client import make_asgi_app
import redis.asyncio as aioredis
from sqlalchemy import text

# Ensure static directories exist before importing/running
os.makedirs(os.path.join("src", "app", "static", "uploads"), exist_ok=True)

from src.app.config import settings
from src.app.database import init_db, get_db
from src.app.middleware import IdempotencyMiddleware, LoggingMetricsMiddleware
from src.app.api.v1.auth import router as auth_router
from src.app.api.v1.sarees import router as sarees_router
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

# Mount static folder
app.mount("/static", StaticFiles(directory="src/app/static"), name="static")

@app.on_event("startup")
async def startup_event():
    # Initialize database tables
    await init_db()

# Serve index.html at root
@app.get("/", response_class=HTMLResponse)
async def read_index():
    index_path = os.path.join("src", "app", "static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return """
    <html>
        <head><title>Zari Saree Catalog</title></head>
        <body style="font-family: sans-serif; text-align: center; padding-top: 100px; background-color: #f7f5f0;">
            <h1 style="color: #800020;">Zari Saree Catalog</h1>
            <p>Frontend is currently building. Please check back in a moment.</p>
            <p><a href="/docs" style="color: #d4af37;">Go to API Docs (/docs)</a></p>
        </body>
    </html>
    """

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check(db=Depends(get_db)):
    # Verify Database Connection
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"failed: {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database healthcheck failed: {str(e)}"
        )
        
    # Verify Redis Connection (Optional/Graceful fallback)
    redis_status = "connected"
    try:
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await client.ping()
        await client.close()
    except Exception as e:
        redis_status = "offline"
        
    return {
        "status": "healthy",
        "database": db_status,
        "redis": redis_status,
        "mode": "sqlite" if "sqlite" in settings.DATABASE_URL else "postgres"
    }

# Include API Routers
app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(sarees_router, prefix=f"{settings.API_V1_STR}/sarees", tags=["sarees"])
app.include_router(admin_router, prefix=f"{settings.API_V1_STR}/admin", tags=["admin"])
