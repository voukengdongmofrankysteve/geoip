"""
tests/conftest.py – Shared pytest fixtures
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import create_app


# ── Fake reader factory ────────────────────────────────────────────────────────

def make_mock_reader(
    lat=37.751, lon=-97.822,
    country="United States", iso="US",
    city="Ashburn", tz="America/Chicago",
    continent="North America",
    region="Virginia", region_code="VA",
    postal="20146",
):
    record = MagicMock()
    record.location.latitude        = lat
    record.location.longitude       = lon
    record.location.accuracy_radius = 1000
    record.location.time_zone       = tz
    record.country.name             = country
    record.country.iso_code         = iso
    record.continent.name           = continent
    record.subdivisions.most_specific.name     = region
    record.subdivisions.most_specific.iso_code = region_code
    record.city.name                = city
    record.postal.code              = postal

    reader = MagicMock()
    reader.__enter__ = MagicMock(return_value=reader)
    reader.__exit__  = MagicMock(return_value=False)
    reader.city      = MagicMock(return_value=record)
    return reader


# ── Shared tmp db path (session-scoped so it is created once) ─────────────────

@pytest.fixture(scope="session")
def mock_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("db") / "GeoLite2-City.mmdb"
    db.touch()
    return db


# ── Test client (function-scoped so patches apply fresh each test) ────────────

@pytest.fixture
def client(mock_db):
    """
    TestClient with:
      - DB path pointing at the temp .mmdb file
      - geoip2.database.Reader replaced by the mock reader
    Both patches are applied at the module level where they are actually used.
    """
    app = create_app()
    with (
        patch("app.geoip.settings.DB_PATH", new=mock_db),
        patch("app.geoip.geoip2.database.Reader", return_value=make_mock_reader()),
    ):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
