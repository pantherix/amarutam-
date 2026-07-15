import asyncio
import pytest
import os
from typing import AsyncGenerator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from unittest.mock import AsyncMock, MagicMock, patch

# Configure environment variables for testing
os.environ["JWT_SECRET"] = "testingsecretkey1234567890123456"
os.environ["FIELD_ENCRYPTION_KEY"] = "3kS2yE0vP4uH9gD5xJ8zM2aQ1wR4tY7uI9oP8aS1dF0="

from src.app.main import app
from src.app.database import get_db
from src.app.models.base import Base

# Setup database url for test
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    pg_host = os.getenv("POSTGRES_HOST")
    if pg_host:
        pg_user = os.getenv("POSTGRES_USER", "postgres")
        pg_pass = os.getenv("POSTGRES_PASSWORD", "postgres")
        pg_db = os.getenv("POSTGRES_DB", "test_amrutam_telemedicine")
        pg_port = os.getenv("POSTGRES_PORT", "5432")
        TEST_DATABASE_URL = f"postgresql+asyncpg://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
    else:
        # Fallback to local SQLite in memory
        TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        from src.app.models import User, Saree, AuditLog
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()

@pytest.fixture(autouse=True)
def mock_redis():
    # Mock Redis client so tests do not require actual Redis server running
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=None)
    mock_client.setex = AsyncMock(return_value=None)
    mock_client.delete = AsyncMock(return_value=None)
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.close = AsyncMock()
    
    # Simple mock pipeline
    mock_pipe = MagicMock()
    mock_pipe.incr = MagicMock()
    mock_pipe.expire = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[1])
    mock_client.pipeline = MagicMock(return_value=mock_pipe)
    
    with patch("redis.asyncio.from_url", return_value=mock_client):
        yield mock_client

@pytest.fixture
async def client(db: AsyncSession, mock_redis) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.state.redis = mock_redis
    
    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def mock_enqueue_task():
    with patch("src.app.worker.enqueue_task") as mock_enqueue:
        yield mock_enqueue
