"""Tests for Lab and LabTest API."""

import pytest


@pytest.mark.django_db
def test_list_labs_includes_clinic_lab(clinic, lab, receptionist, api_client):
    """List labs returns in-clinic lab."""
    api_client.force_authenticate(user=receptionist)
    r = api_client.get("/api/labs/")
    assert r.status_code == 200
    assert any(x["name"] == lab.name for x in r.data)


@pytest.mark.django_db
def test_list_lab_tests(clinic, lab_test, receptionist, api_client):
    """List lab tests returns tests for clinic's lab."""
    api_client.force_authenticate(user=receptionist)
    r = api_client.get("/api/lab-tests/")
    assert r.status_code == 200
    assert any(x["code"] == lab_test.code for x in r.data)


@pytest.mark.django_db
def test_receptionist_cannot_create_lab(receptionist, api_client):
    api_client.force_authenticate(user=receptionist)
    r = api_client.post(
        "/api/labs/",
        {"name": "Frontdesk Lab", "lab_type": "in_clinic"},
        format="json",
    )
    assert r.status_code == 403


@pytest.mark.django_db
def test_clinic_admin_can_create_lab(clinic_admin, api_client):
    api_client.force_authenticate(user=clinic_admin)
    r = api_client.post(
        "/api/labs/",
        {"name": "Clinic Admin Lab", "lab_type": "in_clinic"},
        format="json",
    )
    assert r.status_code == 201
    assert r.data["name"] == "Clinic Admin Lab"


@pytest.mark.django_db
def test_receptionist_cannot_create_lab_test(receptionist, lab, api_client):
    api_client.force_authenticate(user=receptionist)
    r = api_client.post(
        "/api/lab-tests/",
        {"code": "ALT", "name": "Alanine transaminase", "lab": lab.id},
        format="json",
    )
    assert r.status_code == 403
