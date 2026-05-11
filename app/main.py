"""
app/main.py – FastAPI application factory
"""

import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .routers      import geo, health
from .routers      import dashboard as dashboard_router
from .dependencies import limiter, _LoginRequired
from .config       import settings
from .database     import engine
from .models       import Base


def create_app() -> FastAPI:
    # ── Create DB tables on startup ───────────────────────────────────────────
    Base.metadata.create_all(bind=engine)

    app = FastAPI(
        title="GeoLite2 IP Geolocation API",
        description=(
            "Self-hosted, offline-capable IP geolocation powered by MaxMind GeoLite2.\n\n"
            "## Features\n"
            "- 🌍 **Single lookup** – any IP or hostname\n"
            "- 📦 **Batch lookup** – up to 100 targets per request\n"
            "- 🔍 **My IP** – auto-detect and locate the caller\n"
            "- 🔒 **Per-user API tokens** – manage via the dashboard\n"
            "- ⚡ **Rate limiting** – per-token, plan-based limits\n"
            "- 🏠 **Private IP handling** – auto-resolved to real public IP\n"
            "- 📊 **User dashboard** – token management, usage analytics, plan control\n\n"
            "No external API calls needed for lookups — fully offline once the "
            "`.mmdb` database is in place.\n\n"
            "**Dashboard:** [/dashboard](/dashboard)"
        ),
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── Rate limiter ──────────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else [],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # ── Usage logging middleware ──────────────────────────────────────────────
    @app.middleware("http")
    async def log_usage(request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = (time.monotonic() - start) * 1000

        # Only log geo API calls (not dashboard/docs/health)
        path = request.url.path
        if path.startswith("/geo/"):
            try:
                from .database import SessionLocal
                from .models   import UsageLog
                db = SessionLocal()
                try:
                    token_obj = getattr(request.state, "api_token", None)
                    user_obj  = getattr(request.state, "api_user",  None)

                    if user_obj:
                        log = UsageLog(
                            user_id=user_obj.id,
                            token_id=token_obj.id if token_obj else None,
                            endpoint=path,
                            method=request.method,
                            client_ip=request.client.host if request.client else None,
                            status_code=response.status_code,
                            response_ms=round(elapsed_ms, 2),
                        )
                        db.add(log)
                        db.commit()
                finally:
                    db.close()
            except Exception:
                pass  # Never let logging break the response

        return response

    # ── Login-required redirect handler ──────────────────────────────────────
    @app.exception_handler(_LoginRequired)
    async def login_required_handler(request: Request, exc: _LoginRequired):
        resp = RedirectResponse(url="/dashboard/login", status_code=302)
        resp.delete_cookie("session")
        return resp

    # ── Global error handler ──────────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_error_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(exc)},
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(geo.router)
    app.include_router(dashboard_router.router)

    # ── Root → landing page ───────────────────────────────────────────────────
    from fastapi.templating import Jinja2Templates as _Jinja2Templates
    from pathlib import Path as _Path
    from fastapi.responses import HTMLResponse as _HTMLResponse

    _templates = _Jinja2Templates(
        directory=str(_Path(__file__).parent / "templates")
    )

    @app.get("/", include_in_schema=False, response_class=_HTMLResponse)
    async def root(request: Request):
        return _templates.TemplateResponse("landing.html", {"request": request})

    return app


app = create_app()
