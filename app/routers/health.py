"""
app/routers/health.py – Health-check endpoint
"""

from fastapi import APIRouter
from ..schemas import HealthResponse
from ..config  import settings

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
)
async def health():
    db_status = "ok" if settings.DB_PATH.exists() else "missing – download GeoLite2-City.mmdb"
    return HealthResponse(
        status="ok",
        database=db_status,
        version="1.0.0",
    )
