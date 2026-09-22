"""
Application configuration, loaded from environment variables.
Never hardcode secrets here — see .env.example for required vars.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "QueueFlow"
    ENV: str = "development"
    DEBUG: bool = False

    # --- Database ---
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/queueflow"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Auth / JWT ---
    JWT_SECRET_KEY: str = "changeme-generate-a-real-secret-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # --- Rate limiting ---
    RATE_LIMIT_PER_MINUTE: int = 120

    # --- Queue business rules ---
    SMART_ALERT_THRESHOLD: int = 3  # "your turn is approaching" when <= N people ahead
    DEFAULT_AVG_SERVICE_MINUTES: int = 5  # fallback before we have historical data

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sync_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
