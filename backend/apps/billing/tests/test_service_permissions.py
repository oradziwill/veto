import pytest


@pytest.mark.django_db
def test_service_list_allowed_for_receptionist(api_client, receptionist, service):
    api_client.force_authenticate(user=receptionist)
    r = api_client.get("/api/billing/services/")
    assert r.status_code == 200
    assert any(row["id"] == service.id for row in r.data)


@pytest.mark.django_db
def test_service_create_forbidden_for_receptionist(api_client, receptionist):
    api_client.force_authenticate(user=receptionist)
    r = api_client.post(
        "/api/billing/services/",
        {"name": "X-Ray", "code": "XRAY", "price": "200.00"},
        format="json",
    )
    assert r.status_code == 403


@pytest.mark.django_db
def test_service_create_allowed_for_clinic_admin(api_client, clinic_admin):
    api_client.force_authenticate(user=clinic_admin)
    r = api_client.post(
        "/api/billing/services/",
        {"name": "X-Ray", "code": "XRAY", "price": "200.00"},
        format="json",
    )
    assert r.status_code == 201
    assert r.data["name"] == "X-Ray"
