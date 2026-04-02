import pytest
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.clients.models import Client, ClientClinic
from apps.inventory.models import InventoryItem
from apps.medical.models import ProcedureSupplyTemplate, ProcedureSupplyTemplateLine
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.tenancy.models import Clinic
from django.utils import timezone


@pytest.mark.django_db
def test_doctor_creates_procedure_supply_template_with_lines(api_client, doctor, inventory_item):
    assert inventory_item.clinic_id == doctor.clinic_id
    api_client.force_authenticate(user=doctor)
    r = api_client.post(
        "/api/medical/procedure-supply-templates/",
        {
            "name": "USG kit",
            "visit_type": "imaging",
            "is_active": True,
            "lines": [
                {
                    "inventory_item": inventory_item.id,
                    "suggested_quantity": "2",
                    "sort_order": 0,
                    "is_optional": False,
                    "vat_rate": "8",
                    "notes": "",
                }
            ],
        },
        format="json",
    )
    assert r.status_code == 201
    assert r.data["name"] == "USG kit"
    assert len(r.data["lines"]) == 1
    assert r.data["lines"][0]["inventory_item"] == inventory_item.id
    assert AuditLog.objects.filter(
        action="procedure_supply_template_created",
        entity_type="procedure_supply_template",
    ).exists()


@pytest.mark.django_db
def test_doctor_creates_template_with_two_lines(api_client, doctor, inventory_item, clinic):
    item2 = InventoryItem.objects.create(
        clinic=clinic,
        name="Second item",
        sku="SEC-2",
        unit="szt",
        stock_on_hand=5,
        created_by=doctor,
    )
    api_client.force_authenticate(user=doctor)
    r = api_client.post(
        "/api/medical/procedure-supply-templates/",
        {
            "name": "Two-line kit",
            "is_active": True,
            "lines": [
                {
                    "inventory_item": inventory_item.id,
                    "suggested_quantity": "1",
                    "sort_order": 0,
                },
                {
                    "inventory_item": item2.id,
                    "suggested_quantity": "3",
                    "sort_order": 1,
                },
            ],
        },
        format="json",
    )
    assert r.status_code == 201
    assert len(r.data["lines"]) == 2


@pytest.mark.django_db
def test_procedure_supply_template_duplicate_name_rejected(api_client, doctor, inventory_item):
    api_client.force_authenticate(user=doctor)
    body = {
        "name": "Same name",
        "is_active": True,
        "lines": [{"inventory_item": inventory_item.id, "suggested_quantity": "1"}],
    }
    assert (
        api_client.post("/api/medical/procedure-supply-templates/", body, format="json").status_code
        == 201
    )
    dup = api_client.post("/api/medical/procedure-supply-templates/", body, format="json")
    assert dup.status_code == 400
    assert "name" in dup.data


@pytest.mark.django_db
def test_procedure_supply_rejects_inventory_from_other_clinic(api_client, doctor, clinic):
    other = Clinic.objects.create(
        name="Other",
        address="x",
        phone="1",
        email="o@o.com",
    )
    foreign_item = InventoryItem.objects.create(
        clinic=other,
        name="Foreign supply",
        sku="FOR-SUP-1",
        unit="szt",
        stock_on_hand=10,
        created_by=doctor,
    )
    api_client.force_authenticate(user=doctor)
    r = api_client.post(
        "/api/medical/procedure-supply-templates/",
        {
            "name": "Bad kit",
            "is_active": True,
            "lines": [
                {
                    "inventory_item": foreign_item.id,
                    "suggested_quantity": "1",
                }
            ],
        },
        format="json",
    )
    assert r.status_code == 400


@pytest.mark.django_db
def test_receptionist_cannot_crud_procedure_supply_templates(
    api_client, receptionist, inventory_item
):
    api_client.force_authenticate(user=receptionist)
    r = api_client.post(
        "/api/medical/procedure-supply-templates/",
        {
            "name": "X",
            "is_active": True,
            "lines": [{"inventory_item": inventory_item.id, "suggested_quantity": "1"}],
        },
        format="json",
    )
    assert r.status_code == 403


@pytest.mark.django_db
def test_procedure_supply_template_preview(
    api_client, receptionist, doctor, patient, inventory_item, clinic
):
    tpl = ProcedureSupplyTemplate.objects.create(
        clinic=clinic,
        name="Kit A",
        is_active=True,
        created_by=doctor,
    )
    ProcedureSupplyTemplateLine.objects.create(
        template=tpl,
        inventory_item=inventory_item,
        suggested_quantity="1",
        sort_order=0,
        is_optional=False,
    )
    inventory_item.is_active = False
    inventory_item.save(update_fields=["is_active"])

    now = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
    appt = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=now,
        ends_at=now.replace(minute=30),
        status=Appointment.Status.SCHEDULED,
        reason="Visit",
    )

    api_client.force_authenticate(user=receptionist)
    r = api_client.post(
        f"/api/appointments/{appt.id}/procedure-supply-template-preview/",
        {"template_id": tpl.id},
        format="json",
    )
    assert r.status_code == 200
    assert r.data["template_id"] == tpl.id
    assert r.data["template_name"] == "Kit A"
    assert len(r.data["suggested_lines"]) == 1
    row = r.data["suggested_lines"][0]
    assert row["inventory_item_id"] == inventory_item.id
    assert row["inventory_item_is_active"] is False
    assert row["suggested_quantity"] in ("1", "1.000")
    assert row["default_unit_price"] is None


@pytest.mark.django_db
def test_procedure_supply_preview_not_found(api_client, receptionist, appointment):
    api_client.force_authenticate(user=receptionist)
    r = api_client.post(
        f"/api/appointments/{appointment.id}/procedure-supply-template-preview/",
        {"template_id": 999999},
        format="json",
    )
    assert r.status_code == 404


@pytest.mark.django_db
def test_procedure_supply_template_list_filters_by_visit_type(api_client, doctor, clinic):
    ProcedureSupplyTemplate.objects.create(
        clinic=clinic, name="USG A", visit_type="usg", is_active=True, created_by=doctor
    )
    ProcedureSupplyTemplate.objects.create(
        clinic=clinic, name="Other", visit_type="imaging", is_active=True, created_by=doctor
    )
    api_client.force_authenticate(user=doctor)
    r = api_client.get("/api/medical/procedure-supply-templates/?visit_type=usg")
    assert r.status_code == 200
    assert len(r.data) == 1
    assert r.data[0]["name"] == "USG A"


@pytest.mark.django_db
def test_procedure_supply_template_list_visit_type_icontains(api_client, doctor, clinic):
    ProcedureSupplyTemplate.objects.create(
        clinic=clinic, name="T1", visit_type="diagnostic_usg", is_active=True, created_by=doctor
    )
    ProcedureSupplyTemplate.objects.create(
        clinic=clinic, name="T2", visit_type="xray", is_active=True, created_by=doctor
    )
    api_client.force_authenticate(user=doctor)
    r = api_client.get("/api/medical/procedure-supply-templates/?visit_type_icontains=usg")
    assert r.status_code == 200
    assert len(r.data) == 1
    assert r.data[0]["name"] == "T1"


@pytest.mark.django_db
def test_procedure_supply_template_list_for_appointment_wraps_payload(
    api_client, doctor, patient, clinic
):
    tpl = ProcedureSupplyTemplate.objects.create(
        clinic=clinic, name="Kit", visit_type="usg", is_active=True, created_by=doctor
    )
    now = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
    appt = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=now,
        ends_at=now.replace(minute=30),
        status=Appointment.Status.SCHEDULED,
        reason="USG follow-up",
    )
    api_client.force_authenticate(user=doctor)
    r = api_client.get(
        f"/api/medical/procedure-supply-templates/?for_appointment={appt.id}&visit_type=usg"
    )
    assert r.status_code == 200
    assert set(r.data.keys()) == {"appointment_context", "templates"}
    assert r.data["appointment_context"] == {
        "appointment_id": appt.id,
        "patient_id": patient.id,
        "appointment_visit_type": appt.visit_type,
        "reason": "USG follow-up",
    }
    assert len(r.data["templates"]) == 1
    assert r.data["templates"][0]["id"] == tpl.id


@pytest.mark.django_db
def test_procedure_supply_template_list_for_appointment_other_clinic_404(
    api_client, doctor, clinic
):
    other = Clinic.objects.create(
        name="Other",
        address="x",
        phone="1",
        email="o@o.com",
    )
    other_vet = User.objects.create_user(
        username="other_vet", password="pass", clinic=other, is_staff=True, is_vet=True
    )
    owner = Client.objects.create(first_name="O", last_name="P")
    ClientClinic.objects.create(client=owner, clinic=other)
    patient_other = Patient.objects.create(clinic=other, owner=owner, name="Z", species="dog")
    now = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
    appt = Appointment.objects.create(
        clinic=other,
        patient=patient_other,
        vet=other_vet,
        starts_at=now,
        ends_at=now.replace(minute=30),
        status=Appointment.Status.SCHEDULED,
        reason="X",
    )
    api_client.force_authenticate(user=doctor)
    r = api_client.get(f"/api/medical/procedure-supply-templates/?for_appointment={appt.id}")
    assert r.status_code == 404


@pytest.mark.django_db
def test_procedure_supply_template_list_for_appointment_invalid_id_404(api_client, doctor):
    api_client.force_authenticate(user=doctor)
    r = api_client.get("/api/medical/procedure-supply-templates/?for_appointment=not-an-id")
    assert r.status_code == 404


@pytest.mark.django_db
def test_procedure_supply_preview_inactive_template_404(
    api_client, doctor, patient, inventory_item, clinic
):
    tpl = ProcedureSupplyTemplate.objects.create(
        clinic=clinic,
        name="Inactive",
        is_active=False,
        created_by=doctor,
    )
    ProcedureSupplyTemplateLine.objects.create(
        template=tpl,
        inventory_item=inventory_item,
        suggested_quantity="1",
        sort_order=0,
    )
    now = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
    appt = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=now,
        ends_at=now.replace(minute=30),
        status=Appointment.Status.SCHEDULED,
        reason="Visit",
    )
    api_client.force_authenticate(user=doctor)
    r = api_client.post(
        f"/api/appointments/{appt.id}/procedure-supply-template-preview/",
        {"template_id": tpl.id},
        format="json",
    )
    assert r.status_code == 404
