import pytest

from apps.accounts.models import User
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
