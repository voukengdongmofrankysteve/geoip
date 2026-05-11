"""
app/config.py – Centralised settings loaded from .env
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)


class Settings:
    DB_PATH: Path   = Path(os.getenv("GEOIP_DB_PATH", "GeoLite2-City.mmdb"))
    HOST: str       = os.getenv("API_HOST", "0.0.0.0")
    PORT: int       = int(os.getenv("API_PORT", 8074))
    RATE_LIMIT: str = os.getenv("RATE_LIMIT", "60")          # per minute (legacy fallback)
    API_KEY: str    = os.getenv("API_KEY", "")                # blank = disabled
    APP_ENV: str    = os.getenv("APP_ENV", "development")

    # Dashboard / auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-use-a-long-random-string")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./geoip_users.db")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    @property
    def rate_limit_string(self) -> str:
        return f"{self.RATE_LIMIT}/minute"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


settings = Settings()
