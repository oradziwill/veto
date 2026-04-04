import pytest
from apps.audit.models import AuditLog
from apps.patients.models import Patient


@pytest.mark.django_db
def test_patient_create_writes_audit_log(api_client, receptionist, client_with_membership, doctor):
    api_client.force_authenticate(user=receptionist)
    r = api_client.post(
        "/api/patients/",
        {
            "name": "Luna",
            "species": "cat",
            "owner": client_with_membership.id,
            "primary_vet": doctor.id,
        },
        format="json",
    )
    assert r.status_code == 201
    patient = Patient.objects.get(name="Luna", clinic=receptionist.clinic)
    assert AuditLog.objects.filter(
        clinic_id=receptionist.clinic_id,
        action="patient_created",
        entity_type="patient",
        entity_id=str(patient.id),
        after__name="Luna",
    ).exists()


@pytest.mark.django_db
def test_patient_patch_writes_audit_log(api_client, receptionist, patient):
    api_client.force_authenticate(user=receptionist)
    fid = patient.id
    r = api_client.patch(f"/api/patients/{fid}/", {"name": "Luna2"}, format="json")
    assert r.status_code == 200
    row = AuditLog.objects.filter(
        clinic_id=receptionist.clinic_id,
        action="patient_updated",
        entity_type="patient",
        entity_id=str(fid),
    ).first()
    assert row is not None
    assert row.after.get("name") == "Luna2"
