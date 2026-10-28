"""
Application configuration, loaded from environment variables.
Never hardcode secrets here — see .env.example for required vars.
"""
from urllib.parse import urlsplit
from pydantic import model_validator
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

    # --- Browser sessions (HttpOnly cookie + double-submit CSRF) ---
    SESSION_COOKIE_NAME: str = "qf_session"
    CSRF_COOKIE_NAME: str = "qf_csrf"
    SESSION_TTL_HOURS: int = 12
    SESSION_IDLE_MINUTES: int = 120
    COOKIE_SECURE: bool | None = None  # default: True in production, False otherwise
    COOKIE_SAMESITE: str = "lax"
    LOGIN_MAX_FAILURES: int = 5           # per account per window
    LOGIN_FAILURE_WINDOW_SECONDS: int = 900
    AUTH_RATE_LIMIT_PER_MINUTE: int = 20  # per IP on auth routes
    RATE_LIMIT_ENABLED: bool | None = None  # default: disabled only when ENV=test
    PASSWORD_RESET_TTL_MINUTES: int = 30
    PUBLIC_APP_URL: str = "http://localhost:8080"

    # --- Optional email (password reset). Unset = reset emails are not sent. ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_STARTTLS: bool = True

    # --- Realtime / notifications ---
    REALTIME_BACKEND: str = "redis"       # "redis" (multi-instance) or "local"
    TURN_ALERT_MINUTES: int = 20
    QUEUE_MONITOR_INTERVAL_SECONDS: int = 60
    MAX_WS_PER_USER: int = 5

    # --- Wayzen / RAG ---
    EMBEDDING_PROVIDER: str = "local"     # "local" (lexical hashing) or "openai_compatible"
    EMBEDDING_MODEL: str = ""
    EMBEDDING_BASE_URL: str = "https://api.openai.com/v1"
    EMBEDDING_API_KEY: str = ""
    LLM_PROVIDER: str = ""                # "", "anthropic" or "openai_compatible"
    LLM_MODEL: str = ""
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_TIMEOUT_SECONDS: float = 30.0
    LLM_MAX_RETRIES: int = 2
    RAG_TOP_K: int = 5
    RAG_MIN_SCORE: float | None = None  # default depends on the embedding provider
    RAG_MAX_CONTEXT_CHARS: int = 6000
    CHAT_RATE_LIMIT_PER_MINUTE: int = 20
    KNOWLEDGE_DIR: str = ""

    # --- Request limits ---
    MAX_REQUEST_BYTES: int = 1_000_000

    # --- Queue business rules ---
    SMART_ALERT_THRESHOLD: int = 3  # "your turn is approaching" when <= N people ahead
    DEFAULT_AVG_SERVICE_MINUTES: int = 5  # fallback before we have historical data

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production(self):
        if self.ENV == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
            if len(self.JWT_SECRET_KEY) < 32 or self.JWT_SECRET_KEY.startswith("changeme"):
                raise ValueError("Production requires a generated JWT_SECRET_KEY of at least 32 characters")
            if not self.sync_database_url.startswith("postgresql://"):
                raise ValueError("Production requires a synchronous PostgreSQL URL")
            if self.DATABASE_URL == type(self).model_fields["DATABASE_URL"].default:
                raise ValueError("Set DATABASE_URL explicitly for production")
            if not self.REDIS_URL.startswith(("redis://", "rediss://")):
                raise ValueError("Set a valid REDIS_URL")
            if "CORS_ORIGINS" not in self.model_fields_set or not self.cors_origins_list or "*" in self.cors_origins_list:
                raise ValueError("Set explicit CORS_ORIGINS for production")
            if self.COOKIE_SAMESITE.lower() not in ("lax", "strict", "none"):
                raise ValueError("COOKIE_SAMESITE must be lax, strict or none")
            if self.COOKIE_SAMESITE.lower() == "none" and not self.cookie_secure:
                raise ValueError("COOKIE_SAMESITE=none requires secure cookies")
            for origin in self.cors_origins_list:
                url = urlsplit(origin)
                if url.scheme not in ("http", "https") or not url.netloc or url.path or url.query or url.fragment:
                    raise ValueError("CORS_ORIGINS must contain origins without paths")
        return self

    @property
    def cookie_secure(self) -> bool:
        return self.ENV == "production" if self.COOKIE_SECURE is None else self.COOKIE_SECURE

    @property
    def rate_limit_enabled(self) -> bool:
        return self.ENV != "test" if self.RATE_LIMIT_ENABLED is None else self.RATE_LIMIT_ENABLED

    @property
    def llm_configured(self) -> bool:
        return bool(self.LLM_PROVIDER and self.LLM_MODEL and (self.LLM_API_KEY or self.LLM_BASE_URL))

    @property
    def smtp_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_FROM)

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
