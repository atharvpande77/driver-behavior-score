from typing import Optional
from pydantic import computed_field

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    
    APP_PORT: int
    CORS_ALLOWED_ORIGINS: str  # comma-separated list e.g. "https://app.example.com,https://admin.example.com"

    # Deployment environment. Controls sandbox routing and staging-specific guards.
    # Valid values: "development" | "staging" | "production"
    ENVIRONMENT: str = "development"

    DATABASE_URL: Optional[str] = None
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: int
    
    SUREPASS_BASE_URL: str
    SUREPASS_API_KEY: str

    # Surepass sandbox credentials — used when ENVIRONMENT == "staging".
    # If blank, falls back to SUREPASS_BASE_URL / SUREPASS_API_KEY.
    SUREPASS_SANDBOX_BASE_URL: str = ""
    SUREPASS_SANDBOX_API_KEY: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_surepass_base_url(self) -> str:
        """Returns the sandbox Surepass base URL when in staging, otherwise production."""
        if self.ENVIRONMENT == "staging" and self.SUREPASS_SANDBOX_BASE_URL:
            return self.SUREPASS_SANDBOX_BASE_URL
        return self.SUREPASS_BASE_URL

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_surepass_api_key(self) -> str:
        """Returns the sandbox Surepass API key when in staging, otherwise production."""
        if self.ENVIRONMENT == "staging" and self.SUREPASS_SANDBOX_API_KEY:
            return self.SUREPASS_SANDBOX_API_KEY
        return self.SUREPASS_API_KEY
    
    JWT_SECRET: str
    JWT_REFRESH_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRY_SECONDS: int = 900
    JWT_REFRESH_EXPIRY_SECONDS: int = 604800
    
    LOG_LEVEL: str = "INFO"
    LOG_USE_COLORS: bool = True

    # Rate limits for auth endpoints — slowapi limits string format: "N/minute", "N/second", etc.
    # Login: low limit to block credential stuffing without impacting legitimate users.
    # Register: very low — a real user almost never registers more than once.
    # Refresh: higher — browsers refresh silently on every tab load / focus event.
    AUTH_LOGIN_RATE_LIMIT: str = "5/minute"
    AUTH_REGISTER_RATE_LIMIT: str = "3/minute"
    AUTH_REFRESH_RATE_LIMIT: str = "20/minute"

    # Rate limits for public endpoints
    PUBLIC_SCORE_RATE_LIMIT: str = "60/minute"
    PUBLIC_VEHICLES_RATE_LIMIT: str = "60/minute"

    OPENAI_API_KEY: str
    

app_settings = AppSettings()