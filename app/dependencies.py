"""
app/dependencies.py – FastAPI dependencies (auth, rate limiting)
"""

from fastapi import Header, HTTPException, status, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import settings

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Optional API key guard ────────────────────────────────────────────────────
async def verify_api_key(x_api_key: str = Header(default="")):
    """
    If API_KEY is set in .env, every request must include:
        X-API-Key: <your-key>
    If API_KEY is blank, this dependency is a no-op.
    """
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Pass it as the X-API-Key header.",
        )
