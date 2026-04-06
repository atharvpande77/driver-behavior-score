from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    DATABASE_URL: Optional[str] = None
    SUREPASS_BASE_URL: str
    SUREPASS_API_KEY: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRY_SECONDS: int = 900
    JWT_REFRESH_EXPIRY_SECONDS: int = 604800
    LOG_LEVEL: str = "INFO"
    LOG_USE_COLORS: bool = True


app_settings = AppSettings()