"""
tests/test_api.py – API endpoint tests
"""

import pytest
import geoip2.errors
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main  import create_app
from app.geoip import GeoResult
from tests.conftest import make_mock_reader


# ── /health + / ───────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"]  == "ok"
        assert "database"      in data
        assert "version"       in data

    def test_root_lists_endpoints(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "endpoints" in r.json()


# ── GET /geo/{target} ─────────────────────────────────────────────────────────

class TestSingleLookup:
    def test_valid_public_ip(self, client):
        r = client.get("/geo/8.8.8.8")
        assert r.status_code == 200
        data = r.json()
        assert data["ip"]      == "8.8.8.8"
        assert data["country"] == "United States"
        assert data["city"]    == "Ashburn"
        assert data["latitude"]  == 37.751
        assert data["longitude"] == -97.822

    def test_response_contains_all_fields(self, client):
        r = client.get("/geo/1.1.1.1")
        assert r.status_code == 200
        keys = r.json().keys()
        for field in [
            "ip", "country", "country_code", "continent",
            "region", "region_code", "city", "postal_code",
            "latitude", "longitude", "accuracy_km", "timezone",
            "note", "error",
        ]:
            assert field in keys, f"Missing field: {field}"

    def test_private_ip_auto_resolves(self, mock_db):
        """Private IP triggers get_public_ip() and returns geo for the public IP."""
        app = create_app()
        with (
            patch("app.geoip.settings.DB_PATH", new=mock_db),
            patch("app.geoip.geoip2.database.Reader", return_value=make_mock_reader()),
            patch("app.geoip.get_public_ip", return_value="8.8.8.8"),
        ):
            with TestClient(app) as c:
                r = c.get("/geo/192.168.1.1")
        assert r.status_code == 200
        data = r.json()
        assert data["note"] is not None
        assert "private" in data["note"].lower()
        assert data["country"] == "United States"

    def test_hostname_resolves(self, mock_db):
        app = create_app()
        with (
            patch("app.geoip.settings.DB_PATH", new=mock_db),
            patch("app.geoip.geoip2.database.Reader", return_value=make_mock_reader()),
            patch("app.geoip.resolve", return_value="8.8.8.8"),
        ):
            with TestClient(app) as c:
                r = c.get("/geo/google.com")
        assert r.status_code == 200
        assert r.json()["country"] == "United States"

    def test_unknown_ip_returns_error_field(self, mock_db):
        reader = make_mock_reader()
        reader.city.side_effect = geoip2.errors.AddressNotFoundError("not found")
        app = create_app()
        with (
            patch("app.geoip.settings.DB_PATH", new=mock_db),
            patch("app.geoip.geoip2.database.Reader", return_value=reader),
        ):
            with TestClient(app) as c:
                r = c.get("/geo/0.0.0.0")
        assert r.status_code == 200
        assert r.json()["error"] is not None


# ── POST /geo/batch ───────────────────────────────────────────────────────────

class TestBatchLookup:
    def test_batch_two_ips(self, client):
        r = client.post("/geo/batch", json={"targets": ["8.8.8.8", "1.1.1.1"]})
        assert r.status_code == 200
        data = r.json()
        assert data["count"]        == 2
        assert len(data["results"]) == 2

    def test_batch_single_ip(self, client):
        r = client.post("/geo/batch", json={"targets": ["8.8.8.8"]})
        assert r.status_code == 200
        assert r.json()["count"] == 1

    def test_batch_empty_list_rejected(self, client):
        r = client.post("/geo/batch", json={"targets": []})
        assert r.status_code == 422

    def test_batch_mixed_private_public(self, mock_db):
        app = create_app()
        with (
            patch("app.geoip.settings.DB_PATH", new=mock_db),
            patch("app.geoip.geoip2.database.Reader", return_value=make_mock_reader()),
            patch("app.geoip.get_public_ip", return_value="8.8.8.8"),
        ):
            with TestClient(app) as c:
                r = c.post("/geo/batch", json={"targets": ["8.8.8.8", "192.168.1.1"]})
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        # The private-IP result should have a note
        private_result = next(
            (x for x in data["results"] if x.get("note")), None
        )
        assert private_result is not None


# ── GET /geo/me ───────────────────────────────────────────────────────────────

class TestMyIP:
    def test_me_with_forwarded_header(self, mock_db):
        app = create_app()
        with (
            patch("app.geoip.settings.DB_PATH", new=mock_db),
            patch("app.geoip.geoip2.database.Reader", return_value=make_mock_reader()),
        ):
            with TestClient(app) as c:
                r = c.get("/geo/me", headers={"X-Forwarded-For": "8.8.8.8"})
        assert r.status_code == 200
        data = r.json()
        assert data["public_ip"] == "8.8.8.8"
        assert data["geo"]["country"] == "United States"

    def test_me_private_client_fetches_public(self, mock_db):
        """When the test client sends a private IP, the API fetches the real public IP."""
        app = create_app()
        with (
            patch("app.geoip.settings.DB_PATH", new=mock_db),
            patch("app.geoip.geoip2.database.Reader", return_value=make_mock_reader()),
            patch("app.routers.geo.get_public_ip",    return_value="8.8.8.8"),
        ):
            with TestClient(app) as c:
                r = c.get("/geo/me")
        assert r.status_code == 200
        data = r.json()
        assert "public_ip" in data
        assert "geo"        in data

    def test_me_not_swallowed_by_wildcard(self, mock_db):
        """/geo/me must NOT be matched as /geo/{target}='me'."""
        app = create_app()
        with (
            patch("app.geoip.settings.DB_PATH", new=mock_db),
            patch("app.geoip.geoip2.database.Reader", return_value=make_mock_reader()),
            patch("app.routers.geo.get_public_ip",    return_value="8.8.8.8"),
        ):
            with TestClient(app) as c:
                r = c.get("/geo/me")
        # Must return MyIPResponse shape, not GeoResponse shape
        assert "public_ip" in r.json()


# ── API key auth ──────────────────────────────────────────────────────────────

class TestApiKey:
    def test_no_key_needed_by_default(self, client):
        r = client.get("/geo/8.8.8.8")
        assert r.status_code == 200

    def test_missing_key_returns_401(self, mock_db):
        app = create_app()
        with (
            patch("app.dependencies.settings") as ms,
            patch("app.geoip.settings.DB_PATH", new=mock_db),
            patch("app.geoip.geoip2.database.Reader", return_value=make_mock_reader()),
        ):
            ms.API_KEY           = "secret"
            ms.rate_limit_string = "1000/minute"
            ms.is_production     = False
            with TestClient(app) as c:
                r = c.get("/geo/8.8.8.8")
        assert r.status_code == 401

    def test_wrong_key_returns_401(self, mock_db):
        app = create_app()
        with (
            patch("app.dependencies.settings") as ms,
            patch("app.geoip.settings.DB_PATH", new=mock_db),
            patch("app.geoip.geoip2.database.Reader", return_value=make_mock_reader()),
        ):
            ms.API_KEY           = "secret"
            ms.rate_limit_string = "1000/minute"
            ms.is_production     = False
            with TestClient(app) as c:
                r = c.get("/geo/8.8.8.8", headers={"X-API-Key": "wrong"})
        assert r.status_code == 401

    def test_correct_key_returns_200(self, mock_db):
        app = create_app()
        with (
            patch("app.dependencies.settings") as ms,
            patch("app.geoip.settings.DB_PATH", new=mock_db),
            patch("app.geoip.geoip2.database.Reader", return_value=make_mock_reader()),
        ):
            ms.API_KEY           = "secret"
            ms.rate_limit_string = "1000/minute"
            ms.is_production     = False
            with TestClient(app) as c:
                r = c.get("/geo/8.8.8.8", headers={"X-API-Key": "secret"})
        assert r.status_code == 200
