"""
Behavior: Hospital stay + lab order workflow.

Doctor admits patient to hospital, orders lab tests during stay,
enters results, then discharges.
"""

import pytest
from apps.labs.models import LabOrder
from apps.scheduling.models import HospitalStay
from django.utils import timezone


@pytest.mark.django_db
def test_hospital_stay_with_lab_order_workflow(
    doctor,
    patient,
    lab,
    lab_test,
    api_client,
):
    """Admit → order lab → enter result → discharge."""
    api_client.force_authenticate(user=doctor)
    admitted_at = timezone.now()

    # 1. Admit to hospital
    stay_r = api_client.post(
        "/api/hospital-stays/",
        {
            "patient": patient.id,
            "attending_vet": doctor.id,
            "reason": "Post-op monitoring",
            "cage_or_room": "Cage 1",
            "admitted_at": admitted_at.isoformat(),
        },
        format="json",
    )
    assert stay_r.status_code == 201
    stay_id = stay_r.data["id"]

    # 2. Order lab tests (linked to hospital stay)
    order_r = api_client.post(
        "/api/lab-orders/",
        {
            "patient": patient.id,
            "lab": lab.id,
            "hospital_stay": stay_id,
            "clinical_notes": "Daily CBC",
            "lines": [{"test": lab_test.id, "notes": ""}],
        },
        format="json",
    )
    assert order_r.status_code == 201
    order_id = order_r.data["id"]
    line_id = order_r.data["lines"][0]["id"]

    # 3. Send order, enter result
    api_client.post(f"/api/lab-orders/{order_id}/send/", {}, format="json")
    result_r = api_client.post(
        f"/api/lab-orders/{order_id}/enter-result/",
        {
            "order_line_id": line_id,
            "value": "7.5",
            "status": "completed",
        },
        format="json",
    )
    assert result_r.status_code == 200

    # 4. Discharge
    discharge_r = api_client.post(
        f"/api/hospital-stays/{stay_id}/discharge/",
        {"discharge_notes": "Stable, sent home"},
        format="json",
    )
    assert discharge_r.status_code == 200

    stay = HospitalStay.objects.get(pk=stay_id)
    assert stay.status == "discharged"
    order = LabOrder.objects.get(pk=order_id)
    assert order.hospital_stay_id == stay_id
