import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "Amrutam Telemedicine Backend"
    API_V1_STR: str = "/api/v1"
    
    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "amrutam_telemedicine"
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    
    # Security
    JWT_SECRET: str = "supersecretkeychangeinproduction1234567890"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # AES-256 key for field-level encryption (32 bytes base64 encoded)
    # Generate one: base64.b64encode(os.urandom(32)).decode()
    FIELD_ENCRYPTION_KEY: str = "3kS2yE0vP4uH9gD5xJ8zM2aQ1wR4tY7uI9oP8aS1dF0="
    
    # MFA
    MFA_APP_NAME: str = "Amrutam Telemedicine"
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
