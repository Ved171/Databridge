from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://databridge:databridge_secret@localhost:5432/databridge"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Encryption (for storing connector credentials)
    ENCRYPTION_KEY: str = "change-me-32-char-encryption-key!"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()