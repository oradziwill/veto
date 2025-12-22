import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_admin_login_page_resolves():
    client = APIClient()
    resp = client.get("/admin/login/")
    assert resp.status_code in (200, 302)
