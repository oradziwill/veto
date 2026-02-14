"""Tests for Lab Order API."""

import pytest

from apps.labs.models import LabOrder, LabOrderLine, LabResult


@pytest.mark.django_db
def test_doctor_can_create_lab_order(
    doctor,
    patient,
    lab,
    lab_test,
    api_client,
):
    """Doctor can create a lab order with lines."""
    api_client.force_authenticate(user=doctor)

    r = api_client.post(
        "/api/lab-orders/",
        {
            "patient": patient.id,
            "lab": lab.id,
            "clinical_notes": "Check CBC",
            "lines": [{"test": lab_test.id, "notes": ""}],
        },
        format="json",
    )
    assert r.status_code == 201
    assert r.data["status"] == "draft"
    assert len(r.data["lines"]) == 1
    assert r.data["lines"][0]["test_detail"]["code"] == "CBC"


@pytest.mark.django_db
def test_doctor_can_enter_result(
    doctor,
    patient,
    lab,
    lab_test,
    api_client,
):
    """Doctor can enter lab result for an order line."""
    order = LabOrder.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        lab=lab,
        status="sent",
        ordered_by=doctor,
    )
    line = LabOrderLine.objects.create(order=order, test=lab_test)
    LabResult.objects.create(order_line=line)

    api_client.force_authenticate(user=doctor)
    r = api_client.post(
        f"/api/lab-orders/{order.id}/enter-result/",
        {
            "order_line_id": line.id,
            "value": "5.2",
            "status": "completed",
        },
        format="json",
    )
    assert r.status_code == 200
    line.result.refresh_from_db()
    assert line.result.value == "5.2"
    assert line.result.status == "completed"


@pytest.mark.django_db
def test_receptionist_can_list_lab_orders(
    receptionist,
    patient,
    lab,
    doctor,
    api_client,
):
    """Receptionist can list lab orders."""
    LabOrder.objects.create(
        clinic=receptionist.clinic,
        patient=patient,
        lab=lab,
        status="draft",
        ordered_by=doctor,
    )
    api_client.force_authenticate(user=receptionist)
    r = api_client.get("/api/lab-orders/")
    assert r.status_code == 200
    assert len(r.data) >= 1
