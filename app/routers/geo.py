"""
app/routers/geo.py – Geolocation endpoints

IMPORTANT: /me and /batch must be registered BEFORE /{target}
so FastAPI does not swallow them as wildcard path parameters.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..geoip        import lookup, batch_lookup, get_public_ip, is_valid_ip, is_private_ip
from ..schemas      import GeoResponse, BatchRequest, BatchResponse, MyIPResponse
from ..dependencies import verify_api_key, limiter
from ..config       import settings

router = APIRouter(prefix="/geo", tags=["Geolocation"])


# ── GET /geo/me  ──────────────────────────────────────────────────────────────
# Must be FIRST — before /{target} — or FastAPI matches "me" as a path param.
@router.get(
    "/me",
    response_model=MyIPResponse,
    summary="Detect and look up the caller's public IP",
    description=(
        "Auto-detects the caller's IP via X-Forwarded-For or remote address, "
        "then returns full geolocation. Private IPs are transparently resolved "
        "to the server's real public IP."
    ),
)
@limiter.limit(settings.rate_limit_string)
async def my_ip(
    request: Request,
    _auth:   None = Depends(verify_api_key),
):
    forwarded = request.headers.get("X-Forwarded-For")
    client_ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "")
    )

    if not is_valid_ip(client_ip) or is_private_ip(client_ip):
        try:
            client_ip = get_public_ip()
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )

    result = lookup(client_ip)
    return MyIPResponse(
        public_ip=client_ip,
        geo=GeoResponse(**result.to_dict()),
    )


# ── POST /geo/batch ───────────────────────────────────────────────────────────
@router.post(
    "/batch",
    response_model=BatchResponse,
    summary="Look up multiple IPs / hostnames (max 100)",
    description=(
        "Send up to 100 IPs or hostnames in one request. "
        "Private IPs are automatically resolved to the server's public IP."
    ),
)
@limiter.limit(settings.rate_limit_string)
async def lookup_batch(
    request: Request,
    body:    BatchRequest,
    _auth:   None = Depends(verify_api_key),
):
    results = batch_lookup(body.targets)
    return BatchResponse(
        count=len(results),
        results=[GeoResponse(**r.to_dict()) for r in results],
    )


# ── GET /geo/{target}  ────────────────────────────────────────────────────────
# Wildcard — must be LAST so /me and /batch are matched first.
@router.get(
    "/{target}",
    response_model=GeoResponse,
    summary="Look up a single IP or hostname",
    description=(
        "Returns geolocation data for any public IP or hostname. "
        "Private / local IPs (192.168.x, 10.x, 127.x) are automatically "
        "resolved to the server's real public IP."
    ),
)
@limiter.limit(settings.rate_limit_string)
async def lookup_single(
    request: Request,
    target:  str,
    _auth:   None = Depends(verify_api_key),
):
    result = lookup(target)
    return GeoResponse(**result.to_dict())
