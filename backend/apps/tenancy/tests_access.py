import pytest

from apps.accounts.models import User
from apps.tenancy.access import accessible_clinic_ids
from apps.tenancy.models import Clinic, ClinicNetwork


@pytest.mark.django_db
def test_accessible_clinic_ids_single_clinic_user(doctor):
    assert accessible_clinic_ids(doctor) == [doctor.clinic_id]


@pytest.mark.django_db
def test_accessible_clinic_ids_network_admin():
    net = ClinicNetwork.objects.create(name="Chain")
    c1 = Clinic.objects.create(name="C1", network=net, address="a", phone="p", email="e1@test.com")
    c2 = Clinic.objects.create(name="C2", network=net, address="a", phone="p", email="e2@test.com")
    u = User.objects.create_user(
        username="na",
        password="pass",
        role=User.Role.NETWORK_ADMIN,
        network=net,
        is_staff=True,
    )
    assert set(accessible_clinic_ids(u)) == {c1.id, c2.id}


@pytest.mark.django_db
def test_accessible_clinic_ids_network_admin_without_network_returns_empty():
    u = User.objects.create_user(
        username="na2",
        password="pass",
        role=User.Role.NETWORK_ADMIN,
        is_staff=True,
    )
    assert accessible_clinic_ids(u) == []
