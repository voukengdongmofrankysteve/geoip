"""
app/routers/dashboard.py – User dashboard (HTML UI + auth endpoints)
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth       import create_access_token, hash_password, verify_password
from ..database   import get_db
from ..dependencies import get_current_user, get_current_user_optional
from ..models     import ApiToken, PLANS, UsageLog, User

import os
from pathlib import Path

# Templates directory
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["Dashboard"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _redirect_to_login(message: str = "") -> RedirectResponse:
    url = "/dashboard/login"
    if message:
        url += f"?error={message}"
    resp = RedirectResponse(url=url, status_code=302)
    resp.delete_cookie("session")
    return resp


def _get_usage_stats(db: Session, user: User) -> dict:
    """Compute usage statistics for a user."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_requests = db.query(func.count(UsageLog.id)).filter(
        UsageLog.user_id == user.id
    ).scalar() or 0

    monthly_requests = db.query(func.count(UsageLog.id)).filter(
        UsageLog.user_id == user.id,
        UsageLog.created_at >= month_start,
    ).scalar() or 0

    today_requests = db.query(func.count(UsageLog.id)).filter(
        UsageLog.user_id == user.id,
        UsageLog.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
    ).scalar() or 0

    # Last 7 days daily breakdown
    daily_counts = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        count = db.query(func.count(UsageLog.id)).filter(
            UsageLog.user_id == user.id,
            UsageLog.created_at >= day_start,
            UsageLog.created_at <= day_end,
        ).scalar() or 0
        daily_counts.append({"date": day.strftime("%b %d"), "count": count})

    # Endpoint breakdown
    endpoint_stats = (
        db.query(UsageLog.endpoint, func.count(UsageLog.id).label("cnt"))
        .filter(UsageLog.user_id == user.id)
        .group_by(UsageLog.endpoint)
        .order_by(func.count(UsageLog.id).desc())
        .limit(5)
        .all()
    )

    # Recent requests
    recent = (
        db.query(UsageLog)
        .filter(UsageLog.user_id == user.id)
        .order_by(UsageLog.created_at.desc())
        .limit(10)
        .all()
    )

    quota = user.monthly_quota
    quota_pct = min(100, round((monthly_requests / quota) * 100)) if quota else 0

    return {
        "total_requests":   total_requests,
        "monthly_requests": monthly_requests,
        "today_requests":   today_requests,
        "daily_counts":     daily_counts,
        "endpoint_stats":   [{"endpoint": e, "count": c} for e, c in endpoint_stats],
        "recent":           recent,
        "quota":            quota,
        "quota_pct":        quota_pct,
    }


# ── Auth routes ───────────────────────────────────────────────────────────────

@router.get("/dashboard/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = "", success: str = ""):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error":   error,
        "success": success,
    })


@router.post("/dashboard/login")
async def login(
    request: Request,
    email:    str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error":   "Invalid email or password.",
            "success": "",
        }, status_code=400)

    if not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error":   "Account is disabled.",
            "success": "",
        }, status_code=403)

    token = create_access_token({"sub": str(user.id)})
    resp  = RedirectResponse(url="/dashboard", status_code=302)
    resp.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,   # set True in production with HTTPS
        max_age=3600,
    )
    return resp


@router.get("/dashboard/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = ""):
    return templates.TemplateResponse("register.html", {
        "request": request,
        "error":   error,
        "plans":   PLANS,
    })


@router.post("/dashboard/register")
async def register(
    request:  Request,
    username: str = Form(...),
    email:    str = Form(...),
    password: str = Form(...),
    plan:     str = Form(default="free"),
    db: Session = Depends(get_db),
):
    if plan not in PLANS:
        plan = "free"

    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error":   "Email already registered.",
            "plans":   PLANS,
        }, status_code=400)

    if db.query(User).filter(User.username == username).first():
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error":   "Username already taken.",
            "plans":   PLANS,
        }, status_code=400)

    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
        plan=plan,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Auto-create a default token
    token = ApiToken(
        user_id=user.id,
        name="Default Token",
        token=ApiToken.generate(),
    )
    db.add(token)
    db.commit()

    return RedirectResponse(
        url="/dashboard/login?success=Account+created!+You+can+now+log+in.",
        status_code=302,
    )


@router.get("/dashboard/logout")
async def logout():
    resp = RedirectResponse(url="/dashboard/login", status_code=302)
    resp.delete_cookie("session")
    return resp


# ── Dashboard home ────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_home(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats  = _get_usage_stats(db, user)
    tokens = (
        db.query(ApiToken)
        .filter(ApiToken.user_id == user.id)
        .order_by(ApiToken.created_at.desc())
        .all()
    )
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user":    user,
        "stats":   stats,
        "tokens":  tokens,
        "plans":   PLANS,
        "active_page": "overview",
    })


# ── Tokens management ─────────────────────────────────────────────────────────

@router.get("/dashboard/tokens", response_class=HTMLResponse)
async def tokens_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    msg: str = "",
    error: str = "",
):
    tokens = (
        db.query(ApiToken)
        .filter(ApiToken.user_id == user.id)
        .order_by(ApiToken.created_at.desc())
        .all()
    )
    return templates.TemplateResponse("tokens.html", {
        "request": request,
        "user":    user,
        "tokens":  tokens,
        "plans":   PLANS,
        "active_page": "tokens",
        "msg":   msg,
        "error": error,
    })


@router.post("/dashboard/tokens/create")
async def create_token(
    request: Request,
    name: str = Form(...),
    rate_limit_override: Optional[str] = Form(default=None),
    expires_days: Optional[str] = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Count existing tokens
    existing = db.query(ApiToken).filter(ApiToken.user_id == user.id).count()
    max_tokens = {"free": 2, "pro": 10, "enterprise": 50}.get(user.plan, 2)
    if existing >= max_tokens:
        return RedirectResponse(
            url=f"/dashboard/tokens?error=Your+plan+allows+max+{max_tokens}+tokens.",
            status_code=302,
        )

    # Parse rate limit override
    rl_override = None
    if rate_limit_override and rate_limit_override.strip():
        try:
            rl_override = int(rate_limit_override)
            plan_max = user.rate_limit
            if rl_override > plan_max:
                rl_override = plan_max
            if rl_override < 1:
                rl_override = 1
        except ValueError:
            rl_override = None

    # Parse expiry
    expires_at = None
    if expires_days and expires_days.strip():
        try:
            days = int(expires_days)
            if days > 0:
                expires_at = datetime.now(timezone.utc) + timedelta(days=days)
        except ValueError:
            pass

    token = ApiToken(
        user_id=user.id,
        name=name[:100],
        token=ApiToken.generate(),
        rate_limit_override=rl_override,
        expires_at=expires_at,
    )
    db.add(token)
    db.commit()

    return RedirectResponse(
        url=f"/dashboard/tokens?msg=Token+'{name}'+created+successfully.",
        status_code=302,
    )


@router.post("/dashboard/tokens/{token_id}/revoke")
async def revoke_token(
    token_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = db.query(ApiToken).filter(
        ApiToken.id == token_id,
        ApiToken.user_id == user.id,
    ).first()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    token.is_active = False
    db.commit()
    return RedirectResponse(url="/dashboard/tokens?msg=Token+revoked.", status_code=302)


@router.post("/dashboard/tokens/{token_id}/activate")
async def activate_token(
    token_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = db.query(ApiToken).filter(
        ApiToken.id == token_id,
        ApiToken.user_id == user.id,
    ).first()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    token.is_active = True
    db.commit()
    return RedirectResponse(url="/dashboard/tokens?msg=Token+activated.", status_code=302)


@router.post("/dashboard/tokens/{token_id}/delete")
async def delete_token(
    token_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = db.query(ApiToken).filter(
        ApiToken.id == token_id,
        ApiToken.user_id == user.id,
    ).first()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    db.delete(token)
    db.commit()
    return RedirectResponse(url="/dashboard/tokens?msg=Token+deleted.", status_code=302)


@router.post("/dashboard/tokens/{token_id}/update-rate-limit")
async def update_token_rate_limit(
    token_id: int,
    rate_limit: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = db.query(ApiToken).filter(
        ApiToken.id == token_id,
        ApiToken.user_id == user.id,
    ).first()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    try:
        rl = int(rate_limit)
        plan_max = user.rate_limit
        rl = max(1, min(rl, plan_max))
        token.rate_limit_override = rl
        db.commit()
    except ValueError:
        pass

    return RedirectResponse(url="/dashboard/tokens?msg=Rate+limit+updated.", status_code=302)


# ── Usage / Analytics ─────────────────────────────────────────────────────────

@router.get("/dashboard/usage", response_class=HTMLResponse)
async def usage_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats = _get_usage_stats(db, user)
    return templates.TemplateResponse("usage.html", {
        "request": request,
        "user":    user,
        "stats":   stats,
        "plans":   PLANS,
        "active_page": "usage",
    })


# ── Plan management ───────────────────────────────────────────────────────────

@router.get("/dashboard/plan", response_class=HTMLResponse)
async def plan_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    msg: str = "",
):
    return templates.TemplateResponse("plan.html", {
        "request": request,
        "user":    user,
        "plans":   PLANS,
        "active_page": "plan",
        "msg": msg,
    })


@router.post("/dashboard/plan/upgrade")
async def upgrade_plan(
    new_plan: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if new_plan not in PLANS:
        return RedirectResponse(url="/dashboard/plan?msg=Invalid+plan.", status_code=302)

    user.plan = new_plan
    user.updated_at = datetime.now(timezone.utc)
    db.commit()

    return RedirectResponse(
        url=f"/dashboard/plan?msg=Plan+updated+to+{PLANS[new_plan]['display_name']}.",
        status_code=302,
    )


# ── Account settings ──────────────────────────────────────────────────────────

@router.get("/dashboard/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: User = Depends(get_current_user),
    msg: str = "",
    error: str = "",
):
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "user":    user,
        "plans":   PLANS,
        "active_page": "settings",
        "msg":   msg,
        "error": error,
    })


@router.post("/dashboard/settings/password")
async def change_password(
    current_password: str = Form(...),
    new_password:     str = Form(...),
    confirm_password: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(current_password, user.hashed_password):
        return RedirectResponse(
            url="/dashboard/settings?error=Current+password+is+incorrect.",
            status_code=302,
        )
    if new_password != confirm_password:
        return RedirectResponse(
            url="/dashboard/settings?error=New+passwords+do+not+match.",
            status_code=302,
        )
    if len(new_password) < 8:
        return RedirectResponse(
            url="/dashboard/settings?error=Password+must+be+at+least+8+characters.",
            status_code=302,
        )
    user.hashed_password = hash_password(new_password)
    db.commit()
    return RedirectResponse(
        url="/dashboard/settings?msg=Password+changed+successfully.",
        status_code=302,
    )
