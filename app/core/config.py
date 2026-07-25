import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "ClubHub API"
    DEBUG: bool = True

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/clubhub_db"
    JWT_SECRET: str = "supersecretjwtkey_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
