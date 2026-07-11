from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.app.config import settings
from src.app.models.base import Base

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db() -> None:
    # Convenient helper to create tables in SQLite/Postgres for local verification and testing
    async with engine.begin() as conn:
        # Import entities here to register them with Base
        from src.app.models import User, Profile, Doctor, AvailabilitySlot, Consultation, Prescription, Payment, AuditLog
        await conn.run_sync(Base.metadata.create_all)
