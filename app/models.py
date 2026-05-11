"""
app/models.py – SQLAlchemy ORM models
"""

import secrets
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, Text, Float
)
from sqlalchemy.orm import relationship

from .database import Base


# ── Plans ─────────────────────────────────────────────────────────────────────

PLANS = {
    "free": {
        "display_name": "Free",
        "rate_limit": 10,          # requests per minute
        "batch_limit": 10,         # max IPs per batch
        "monthly_quota": 1_000,    # total requests/month
        "price": 0,
        "color": "gray",
        "features": [
            "10 requests / minute",
            "10 IPs per batch",
            "1,000 requests / month",
            "Basic geolocation data",
            "Community support",
        ],
    },
    "pro": {
        "display_name": "Pro",
        "rate_limit": 60,
        "batch_limit": 50,
        "monthly_quota": 50_000,
        "price": 9,
        "color": "blue",
        "features": [
            "60 requests / minute",
            "50 IPs per batch",
            "50,000 requests / month",
            "Full geolocation data",
            "Email support",
            "Usage analytics",
        ],
    },
    "enterprise": {
        "display_name": "Enterprise",
        "rate_limit": 300,
        "batch_limit": 100,
        "monthly_quota": 500_000,
        "price": 49,
        "color": "purple",
        "features": [
            "300 requests / minute",
            "100 IPs per batch",
            "500,000 requests / month",
            "Full geolocation data",
            "Priority support",
            "Usage analytics",
            "Custom rate limits",
            "SLA guarantee",
        ],
    },
}


# ── User ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    email           = Column(String(255), unique=True, index=True, nullable=False)
    username        = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    plan            = Column(String(50), default="free", nullable=False)
    is_active       = Column(Boolean, default=True)
    is_admin        = Column(Boolean, default=False)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc))

    tokens = relationship("ApiToken", back_populates="user", cascade="all, delete-orphan")
    usage  = relationship("UsageLog",  back_populates="user", cascade="all, delete-orphan")

    @property
    def plan_details(self) -> dict:
        return PLANS.get(self.plan, PLANS["free"])

    @property
    def rate_limit(self) -> int:
        return self.plan_details["rate_limit"]

    @property
    def batch_limit(self) -> int:
        return self.plan_details["batch_limit"]

    @property
    def monthly_quota(self) -> int:
        return self.plan_details["monthly_quota"]


# ── API Token ─────────────────────────────────────────────────────────────────

class ApiToken(Base):
    __tablename__ = "api_tokens"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    name            = Column(String(100), nullable=False)
    token           = Column(String(64), unique=True, index=True, nullable=False)
    is_active       = Column(Boolean, default=True)
    rate_limit_override = Column(Integer, nullable=True)   # None = use plan default
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_used_at    = Column(DateTime, nullable=True)
    expires_at      = Column(DateTime, nullable=True)      # None = never expires

    user  = relationship("User",     back_populates="tokens")
    usage = relationship("UsageLog", back_populates="token", cascade="all, delete-orphan")

    @staticmethod
    def generate() -> str:
        return "gip_" + secrets.token_hex(28)

    @property
    def effective_rate_limit(self) -> int:
        if self.rate_limit_override is not None:
            return self.rate_limit_override
        return self.user.rate_limit if self.user else 10

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at.replace(tzinfo=timezone.utc)

    @property
    def masked(self) -> str:
        """Show only first 8 and last 4 chars."""
        if len(self.token) <= 12:
            return self.token
        return self.token[:8] + "••••••••" + self.token[-4:]


# ── Usage Log ─────────────────────────────────────────────────────────────────

class UsageLog(Base):
    __tablename__ = "usage_logs"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_id   = Column(Integer, ForeignKey("api_tokens.id"), nullable=True)
    endpoint   = Column(String(100), nullable=False)
    method     = Column(String(10), nullable=False, default="GET")
    client_ip  = Column(String(45), nullable=True)
    status_code = Column(Integer, nullable=True)
    response_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user  = relationship("User",     back_populates="usage")
    token = relationship("ApiToken", back_populates="usage")
