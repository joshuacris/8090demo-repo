"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://localhost:5432/vault"
    JWT_SECRET: str = "dev-secret-change-in-prod"
    JWT_ALGORITHM: str = "HS256"
    DEBUG: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
