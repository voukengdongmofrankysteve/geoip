"""
app/config.py – Centralised settings loaded from .env
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DB_PATH: Path   = Path(os.getenv("GEOIP_DB_PATH", "GeoLite2-City.mmdb"))
    HOST: str       = os.getenv("API_HOST", "0.0.0.0")
    PORT: int       = int(os.getenv("API_PORT", 8000))
    RATE_LIMIT: str = os.getenv("RATE_LIMIT", "60")          # per minute
    API_KEY: str    = os.getenv("API_KEY", "")                # blank = disabled
    APP_ENV: str    = os.getenv("APP_ENV", "development")

    @property
    def rate_limit_string(self) -> str:
        return f"{self.RATE_LIMIT}/minute"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


settings = Settings()
