import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_admin_url_resolves(client):
    resp = client.get("/admin/login/")
    assert resp.status_code in (200, 302)
