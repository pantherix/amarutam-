import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "Vastra Aishwarya Saree Platform"
    API_V1_STR: str = "/api/v1"
    
    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "saree_catalog"
    
    # SQLite fallback file
    SQLITE_DB_FILE: str = "saree_catalog.db"
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    
    # Security
    JWT_SECRET: str = "supersecretkeychangeinproduction1234567890"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours for admin convenience
    
    # AES-256 key for field-level encryption (32 bytes base64 encoded)
    FIELD_ENCRYPTION_KEY: str = "3kS2yE0vP4uH9gD5xJ8zM2aQ1wR4tY7uI9oP8aS1dF0="
    
    # WhatsApp Configuration
    WHATSAPP_PHONE_NUMBER: str = "919876543210"  # Target WhatsApp number for orders
    
    # Analytics
    GOOGLE_ANALYTICS_ID: Optional[str] = None
    
    @property
    def DATABASE_URL(self) -> str:
        # If POSTGRES_HOST is not set, default to SQLite
        if not self.POSTGRES_HOST:
            return f"sqlite+aiosqlite:///./{self.SQLITE_DB_FILE}"
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
