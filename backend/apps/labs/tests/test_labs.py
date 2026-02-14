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
