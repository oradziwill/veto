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


@pytest.mark.django_db
def test_accessible_clinic_ids_superuser_includes_all_clinics():
    c1 = Clinic.objects.create(name="S1", address="a", phone="p", email="a@test.com")
    c2 = Clinic.objects.create(name="S2", address="a", phone="p", email="b@test.com")
    su = User.objects.create_superuser(username="su1", password="x", email="su@test.com")
    assert set(accessible_clinic_ids(su)) == {c1.id, c2.id}


@pytest.mark.django_db
def test_superuser_clinic_ids_cache_invalidates_when_clinic_added():
    from django.core.cache import cache

    from apps.tenancy.access import SUPERUSER_CLINIC_IDS_CACHE_KEY

    c1 = Clinic.objects.create(name="S1", address="a", phone="p", email="a@test.com")
    su = User.objects.create_superuser(username="su2", password="x", email="su2@test.com")
    assert set(accessible_clinic_ids(su)) == {c1.id}
    assert cache.get(SUPERUSER_CLINIC_IDS_CACHE_KEY) is not None

    c2 = Clinic.objects.create(name="S2", address="a", phone="p", email="b@test.com")
    assert cache.get(SUPERUSER_CLINIC_IDS_CACHE_KEY) is None
    assert set(accessible_clinic_ids(su)) == {c1.id, c2.id}


@pytest.mark.django_db
def test_network_admin_clinic_ids_cache_invalidates_when_clinic_added_to_network():
    from django.core.cache import cache

    from apps.tenancy.access import network_clinic_ids_cache_key

    net = ClinicNetwork.objects.create(name="ChainZ")
    c1 = Clinic.objects.create(name="NZ1", network=net, address="a", phone="p", email="n1@test.com")
    u = User.objects.create_user(
        username="na_z",
        password="pass",
        role=User.Role.NETWORK_ADMIN,
        network=net,
        is_staff=True,
    )
    assert set(accessible_clinic_ids(u)) == {c1.id}
    assert cache.get(network_clinic_ids_cache_key(net.id)) is not None

    c2 = Clinic.objects.create(name="NZ2", network=net, address="a", phone="p", email="n2@test.com")
    assert cache.get(network_clinic_ids_cache_key(net.id)) is None
    assert set(accessible_clinic_ids(u)) == {c1.id, c2.id}
