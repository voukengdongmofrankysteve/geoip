"""
app/dependencies.py – FastAPI dependencies (auth, rate limiting, dashboard session)
"""

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from .config   import settings
from .database import get_db
from .auth     import decode_access_token

# ── Rate limiter (keyed by API token when present, else by IP) ────────────────

def _get_rate_limit_key(request: Request) -> str:
    """Use the X-API-Key token value as the rate-limit key when present."""
    token = request.headers.get("X-API-Key", "").strip()
    if token:
        return f"token:{token}"
    return get_remote_address(request)


limiter = Limiter(key_func=_get_rate_limit_key)


# ── API key guard (per-token, DB-backed) ──────────────────────────────────────

async def verify_api_key(
    request: Request,
    x_api_key: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """
    Validates the X-API-Key header against the database.
    Falls back to the legacy single-key check if no users exist yet.
    Also attaches the resolved token and user to request.state for downstream use.
    """
    from .models import ApiToken
    from datetime import datetime, timezone

    # ── Legacy single-key fallback (backward compat) ──────────────────────────
    if settings.API_KEY:
        if x_api_key == settings.API_KEY:
            request.state.api_token = None
            request.state.api_user  = None
            return
        # If a legacy key is configured, also allow DB tokens
        if not x_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key. Pass it as the X-API-Key header.",
            )

    # ── DB token lookup ───────────────────────────────────────────────────────
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Pass it as the X-API-Key header.",
        )

    token_obj = (
        db.query(ApiToken)
        .filter(ApiToken.token == x_api_key, ApiToken.is_active == True)
        .first()
    )

    if not token_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key.",
        )

    if token_obj.is_expired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired.",
        )

    if not token_obj.user or not token_obj.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled.",
        )

    # Update last_used_at
    token_obj.last_used_at = datetime.now(timezone.utc)
    db.commit()

    request.state.api_token = token_obj
    request.state.api_user  = token_obj.user


# ── Dashboard session dependency ──────────────────────────────────────────────

from fastapi.responses import RedirectResponse


class _LoginRequired(Exception):
    """Sentinel raised when a dashboard route needs authentication."""
    pass


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Reads the JWT from the 'session' cookie and returns the current User.
    Raises _LoginRequired (caught by the app-level handler → redirect to login).
    """
    from .models import User

    session_token = request.cookies.get("session")
    if not session_token:
        raise _LoginRequired()

    payload = decode_access_token(session_token)
    if not payload:
        raise _LoginRequired()

    user_id = payload.get("sub")
    if not user_id:
        raise _LoginRequired()

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise _LoginRequired()

    return user


async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
):
    """Same as get_current_user but returns None instead of raising."""
    from .models import User

    session_token = request.cookies.get("session")
    if not session_token:
        return None

    payload = decode_access_token(session_token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        return None

    return user
