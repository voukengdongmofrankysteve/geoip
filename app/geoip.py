"""
app/geoip.py – Core GeoLite2 lookup logic
"""

import socket
import requests
import geoip2.database
import geoip2.errors
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

from .config import settings


# ── Private / reserved IP prefixes ────────────────────────────────────────────
_PRIVATE_PREFIXES = (
    "10.", "127.", "169.254.",
    "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.",
    "172.24.", "172.25.", "172.26.", "172.27.",
    "172.28.", "172.29.", "172.30.", "172.31.",
    "192.168.",
    "::1", "fc00:", "fd", "fe80:",
)


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class GeoResult:
    ip:           str
    country:      Optional[str]   = None
    country_code: Optional[str]   = None
    continent:    Optional[str]   = None
    region:       Optional[str]   = None
    region_code:  Optional[str]   = None
    city:         Optional[str]   = None
    postal_code:  Optional[str]   = None
    latitude:     Optional[float] = None
    longitude:    Optional[float] = None
    accuracy_km:  Optional[int]   = None
    timezone:     Optional[str]   = None
    note:         Optional[str]   = None
    error:        Optional[str]   = None

    def to_dict(self) -> dict:
        return asdict(self)

    def is_ok(self) -> bool:
        return self.error is None


# ── Helpers ────────────────────────────────────────────────────────────────────

def is_valid_ip(address: str) -> bool:
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(family, address)
            return True
        except socket.error:
            continue
    return False


def is_private_ip(address: str) -> bool:
    return any(address.startswith(p) for p in _PRIVATE_PREFIXES)


def get_public_ip(timeout: int = 5) -> str:
    """Fetch real public IP via multiple fallback services."""
    for url in [
        "https://api.ipify.org",
        "https://ipinfo.io/ip",
        "https://icanhazip.com",
    ]:
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            ip = resp.text.strip()
            if is_valid_ip(ip):
                return ip
        except Exception:
            continue
    raise RuntimeError("Could not determine public IP. Check internet connection.")


def resolve(hostname: str) -> str:
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve '{hostname}': {exc}") from exc


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_db_path(db_path: Optional[Path]) -> Path:
    """Return db_path if given, otherwise read from settings at call time (not import time)."""
    return db_path if db_path is not None else settings.DB_PATH


def _query(reader: geoip2.database.Reader, ip: str) -> GeoResult:
    """Run a single city query on an open reader. Never raises."""
    try:
        r = reader.city(ip)
        return GeoResult(
            ip=ip,
            country=r.country.name,
            country_code=r.country.iso_code,
            continent=r.continent.name,
            region=r.subdivisions.most_specific.name if r.subdivisions else None,
            region_code=r.subdivisions.most_specific.iso_code if r.subdivisions else None,
            city=r.city.name,
            postal_code=r.postal.code,
            latitude=r.location.latitude,
            longitude=r.location.longitude,
            accuracy_km=r.location.accuracy_radius,
            timezone=r.location.time_zone,
        )
    except geoip2.errors.AddressNotFoundError:
        return GeoResult(ip=ip, error="Address not found (private/reserved IP?)")
    except Exception as exc:
        return GeoResult(ip=ip, error=str(exc))


def _resolve_to_public(target: str) -> tuple[str, Optional[str]]:
    """
    Resolve target → (final_ip, note).
    Swaps private/local IPs for the machine's real public IP.
    """
    original = target

    if not is_valid_ip(target):
        target = resolve(target)   # raises ValueError on failure

    if is_private_ip(target):
        public = get_public_ip()   # raises RuntimeError on failure
        note = (
            f"'{original}' is a private/local IP. "
            f"Looked up your real public IP instead: {public}"
        )
        return public, note

    return target, None


# ── Public API ─────────────────────────────────────────────────────────────────

def lookup(target: str, db_path: Optional[Path] = None) -> GeoResult:
    """
    Look up a single IP or hostname.
    db_path defaults to settings.DB_PATH (read lazily, so patching works in tests).
    """
    resolved_db = _get_db_path(db_path)

    try:
        ip, note = _resolve_to_public(target)
    except (ValueError, RuntimeError) as exc:
        return GeoResult(ip=target, error=str(exc))

    if not resolved_db.exists():
        return GeoResult(ip=ip, error=f"Database not found: {resolved_db}")

    with geoip2.database.Reader(str(resolved_db)) as reader:
        result = _query(reader, ip)

    result.note = note
    return result


def batch_lookup(targets: list[str], db_path: Optional[Path] = None) -> list[GeoResult]:
    """
    Look up multiple IPs / hostnames, sharing one reader.
    Private IPs are resolved to the machine's public IP (fetched at most once).
    """
    resolved_db = _get_db_path(db_path)

    if not resolved_db.exists():
        return [GeoResult(ip=t, error=f"Database not found: {resolved_db}") for t in targets]

    _public_ip:  Optional[str] = None
    _public_err: Optional[str] = None

    # Pre-resolve all targets
    resolved: list[tuple[str, str, Optional[str]]] = []  # (original, final_ip, note)
    for target in targets:
        original = target
        try:
            if not is_valid_ip(target):
                target = resolve(target)

            if is_private_ip(target):
                if _public_ip is None and _public_err is None:
                    try:
                        _public_ip = get_public_ip()
                    except RuntimeError as exc:
                        _public_err = str(exc)

                if _public_ip:
                    note = (
                        f"'{original}' is a private/local IP. "
                        f"Looked up your real public IP instead: {_public_ip}"
                    )
                    resolved.append((original, _public_ip, note))
                else:
                    resolved.append((original, f"__ERR__Private IP; {_public_err}", None))
            else:
                resolved.append((original, target, None))

        except ValueError as exc:
            resolved.append((original, f"__ERR__{exc}", None))

    results: list[GeoResult] = []
    with geoip2.database.Reader(str(resolved_db)) as reader:
        for original, ip, note in resolved:
            if ip.startswith("__ERR__"):
                results.append(GeoResult(ip=original, error=ip[7:]))
                continue
            result = _query(reader, ip)
            result.note = note
            results.append(result)

    return results
