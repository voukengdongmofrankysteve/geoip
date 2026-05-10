"""
app/main.py – FastAPI application factory
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .routers      import geo, health
from .dependencies import limiter
from .config       import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="GeoLite2 IP Geolocation API",
        description=(
            "Self-hosted, offline-capable IP geolocation powered by MaxMind GeoLite2.\n\n"
            "## Features\n"
            "- 🌍 **Single lookup** – any IP or hostname\n"
            "- 📦 **Batch lookup** – up to 100 targets per request\n"
            "- 🔍 **My IP** – auto-detect and locate the caller\n"
            "- 🔒 **Optional API key** – set `API_KEY` in `.env`\n"
            "- ⚡ **Rate limiting** – configurable per-IP limits\n"
            "- 🏠 **Private IP handling** – auto-resolved to real public IP\n\n"
            "No external API calls needed for lookups — fully offline once the "
            "`.mmdb` database is in place."
        ),
        version="1.0.0",
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

    # ── Root redirect info ────────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "service": "GeoLite2 IP Geolocation API",
            "version": "1.0.0",
            "docs":    "/docs",
            "redoc":   "/redoc",
            "health":  "/health",
            "endpoints": {
                "single":  "GET  /geo/{ip_or_hostname}",
                "batch":   "POST /geo/batch",
                "my_ip":   "GET  /geo/me",
            },
        }

    return app


app = create_app()
