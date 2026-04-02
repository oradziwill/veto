from unittest.mock import patch

import pytest
from rest_framework.test import APIClient


def test_health_ping_no_db():
    client = APIClient()
    resp = client.get("/health/")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@pytest.mark.django_db
def test_health_ready_database_ok():
    client = APIClient()
    resp = client.get("/health/ready/")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "checks": {"database": True}}


@patch("config.health.connection")
def test_health_ready_returns_503_when_database_unreachable(mock_connection):
    mock_connection.ensure_connection.side_effect = RuntimeError("db down")
    client = APIClient()
    resp = client.get("/health/ready/")
    assert resp.status_code == 503
    assert resp.json() == {"ok": False, "checks": {"database": False}}


@pytest.mark.django_db
def test_admin_login_page_resolves():
    client = APIClient()
    resp = client.get("/admin/login/")
    assert resp.status_code in (200, 302)
