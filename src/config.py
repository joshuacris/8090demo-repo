"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://localhost:5432/teampulse"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    DEBUG: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
