import pytest
from django.urls import reverse

from apps.audit.models import AuditLog


@pytest.mark.django_db
def test_audit_log_list_is_admin_only(api_client, clinic_admin, receptionist):
    api_client.force_authenticate(user=receptionist)
    forbidden = api_client.get(reverse("audit-logs-list"))
    assert forbidden.status_code == 403

    api_client.force_authenticate(user=clinic_admin)
    ok = api_client.get(reverse("audit-logs-list"))
    assert ok.status_code == 200


@pytest.mark.django_db
def test_close_visit_writes_audit_log(api_client, doctor, appointment):
    api_client.force_authenticate(user=doctor)
    response = api_client.post(
        f"/api/appointments/{appointment.id}/close-visit/", {}, format="json"
    )
    assert response.status_code in (200, 204)

    event = AuditLog.objects.filter(
        clinic_id=doctor.clinic_id,
        action="visit_closed",
        entity_type="appointment",
        entity_id=str(appointment.id),
    ).first()
    assert event is not None
    assert event.after.get("status") == "completed"


@pytest.mark.django_db
def test_clinic_user_create_writes_audit_log(api_client, clinic_admin):
    api_client.force_authenticate(user=clinic_admin)
    response = api_client.post(
        reverse("users-list"),
        {
            "username": "audit_user",
            "password": "secure-pass",
            "role": "receptionist",
            "is_active": True,
        },
        format="json",
    )
    assert response.status_code == 201

    created_user_id = response.data["id"]
    event = AuditLog.objects.filter(
        clinic_id=clinic_admin.clinic_id,
        action="clinic_user_created",
        entity_type="user",
        entity_id=str(created_user_id),
    ).first()
    assert event is not None
