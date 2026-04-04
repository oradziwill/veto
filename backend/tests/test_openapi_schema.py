from rest_framework.test import APIClient


def test_openapi_schema_succeeds_without_auth_when_debug():
    client = APIClient()
    resp = client.get("/api/schema/")
    assert resp.status_code == 200
    body = resp.content.decode("utf-8")
    assert "openapi" in body
