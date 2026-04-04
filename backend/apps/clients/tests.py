import pytest

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.clients.models import Client, ClientClinic
from apps.tenancy.models import Clinic


@pytest.mark.django_db
def test_clients_list_default_scoped_to_current_clinic(api_client, receptionist):
    clinic_a = receptionist.clinic
    clinic_b = Clinic.objects.create(name="Clinic B", address="b", phone="2", email="b@c.com")
    client_a = Client.objects.create(first_name="Alice", last_name="A")
    client_b = Client.objects.create(first_name="Bob", last_name="B")
    ClientClinic.objects.create(client=client_a, clinic=clinic_a, is_active=True)
    ClientClinic.objects.create(client=client_b, clinic=clinic_b, is_active=True)

    api_client.force_authenticate(user=receptionist)
    r = api_client.get("/api/clients/")
    assert r.status_code == 200
    ids = {row["id"] for row in r.data}
    assert client_a.id in ids
    assert client_b.id not in ids


@pytest.mark.django_db
def test_client_create_auto_links_membership(api_client, receptionist):
    api_client.force_authenticate(user=receptionist)
    r = api_client.post(
        "/api/clients/",
        {"first_name": "John", "last_name": "Doe", "email": "john@example.com"},
        format="json",
    )
    assert r.status_code == 201
    assert ClientClinic.objects.filter(
        client_id=r.data["id"], clinic_id=receptionist.clinic_id, is_active=True
    ).exists()
    assert AuditLog.objects.filter(
        clinic_id=receptionist.clinic_id,
        action="client_created",
        entity_type="client",
        entity_id=str(r.data["id"]),
    ).exists()


@pytest.mark.django_db
def test_client_update_writes_audit_log(api_client, receptionist, client_with_membership):
    api_client.force_authenticate(user=receptionist)
    r = api_client.patch(
        f"/api/clients/{client_with_membership.id}/",
        {"phone": "+48111222333"},
        format="json",
    )
    assert r.status_code == 200
    row = AuditLog.objects.filter(
        clinic_id=receptionist.clinic_id,
        action="client_updated",
        entity_type="client",
        entity_id=str(client_with_membership.id),
    ).first()
    assert row is not None
    assert row.after.get("phone") == "+48111222333"


@pytest.mark.django_db
def test_client_delete_without_patients_writes_audit_log(api_client, receptionist):
    lone = Client.objects.create(first_name="Solo", last_name="Owner")
    ClientClinic.objects.create(client=lone, clinic=receptionist.clinic, is_active=True)
    api_client.force_authenticate(user=receptionist)
    r = api_client.delete(f"/api/clients/{lone.id}/")
    assert r.status_code == 204
    assert AuditLog.objects.filter(
        clinic_id=receptionist.clinic_id,
        action="client_deleted",
        entity_type="client",
        entity_id=str(lone.id),
    ).exists()


@pytest.mark.django_db
def test_client_membership_create_writes_audit_log(api_client, receptionist):
    client = Client.objects.create(first_name="New", last_name="Member")
    api_client.force_authenticate(user=receptionist)
    r = api_client.post(
        "/api/client-memberships/",
        {"client": client.id, "is_active": True},
        format="json",
    )
    assert r.status_code == 201
    assert AuditLog.objects.filter(
        clinic_id=receptionist.clinic_id,
        action="client_membership_created",
        entity_type="client_clinic",
        entity_id=str(r.data["id"]),
    ).exists()


@pytest.mark.django_db
def test_client_membership_patch_cannot_reassign_clinic(api_client, receptionist):
    other_clinic = Clinic.objects.create(name="Clinic X", address="x", phone="3", email="x@c.com")
    client = Client.objects.create(first_name="Owner", last_name="One")
    membership = ClientClinic.objects.create(
        client=client, clinic=receptionist.clinic, is_active=True
    )

    api_client.force_authenticate(user=receptionist)
    r = api_client.patch(
        f"/api/client-memberships/{membership.id}/",
        {"clinic": other_clinic.id, "is_active": False},
        format="json",
    )
    assert r.status_code == 200
    membership.refresh_from_db()
    assert membership.clinic_id == receptionist.clinic_id
    assert membership.is_active is False


@pytest.mark.django_db
def test_clients_require_clinic_membership(api_client):
    user_without_clinic = User.objects.create_user(
        username="no_clinic_user",
        password="pass",
        role=User.Role.RECEPTIONIST,
    )
    api_client.force_authenticate(user=user_without_clinic)
    r = api_client.get("/api/clients/")
    assert r.status_code == 403


@pytest.mark.django_db
def test_client_memberships_list_scoped_to_current_clinic(api_client, receptionist):
    clinic_a = receptionist.clinic
    clinic_b = Clinic.objects.create(name="Clinic C", address="c", phone="4", email="c@c.com")
    shared_client = Client.objects.create(first_name="Shared", last_name="Owner")
    own_membership = ClientClinic.objects.create(
        client=shared_client, clinic=clinic_a, is_active=True
    )
    other_membership = ClientClinic.objects.create(
        client=shared_client, clinic=clinic_b, is_active=True
    )

    api_client.force_authenticate(user=receptionist)
    r = api_client.get("/api/client-memberships/")
    assert r.status_code == 200
    ids = {row["id"] for row in r.data}
    assert own_membership.id in ids
    assert other_membership.id not in ids


@pytest.mark.django_db
def test_client_membership_create_ignores_foreign_clinic_input(api_client, receptionist):
    foreign_clinic = Clinic.objects.create(name="Clinic D", address="d", phone="5", email="d@c.com")
    client = Client.objects.create(first_name="Jane", last_name="Owner")

    api_client.force_authenticate(user=receptionist)
    r = api_client.post(
        "/api/client-memberships/",
        {"client": client.id, "clinic": foreign_clinic.id, "is_active": True},
        format="json",
    )
    assert r.status_code == 201
    assert r.data["clinic"] == receptionist.clinic_id


@pytest.mark.django_db
def test_gdpr_export_admin_only(api_client, clinic_admin, receptionist, client_with_membership):
    api_client.force_authenticate(user=receptionist)
    r = api_client.get(f"/api/clients/{client_with_membership.id}/gdpr-export/")
    assert r.status_code == 403

    api_client.force_authenticate(user=clinic_admin)
    r2 = api_client.get(f"/api/clients/{client_with_membership.id}/gdpr-export/")
    assert r2.status_code == 200
    assert r2.data["client"]["email"] == client_with_membership.email
    assert r2.data["clinic_id"] == clinic_admin.clinic_id
    assert AuditLog.objects.filter(
        action="client_gdpr_export_downloaded",
        entity_id=str(client_with_membership.id),
    ).exists()
