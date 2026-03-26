import pytest
from apps.accounts.models import User
from apps.tenancy.models import Clinic
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_clinic_admin_can_create_user_in_own_clinic():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    admin = User.objects.create_user(
        username="admin1",
        password="pass",
        clinic=clinic,
        is_staff=True,
        role=User.Role.ADMIN,
    )
    client = APIClient()
    client.force_authenticate(user=admin)

    resp = client.post(
        reverse("users-list"),
        {
            "username": "new_receptionist",
            "password": "secret-pass",
            "first_name": "Ada",
            "last_name": "Nowak",
            "email": "ada@example.com",
            "role": User.Role.RECEPTIONIST,
            "is_active": True,
        },
        format="json",
    )
    assert resp.status_code == 201

    created = User.objects.get(username="new_receptionist")
    assert created.clinic_id == clinic.id
    assert created.role == User.Role.RECEPTIONIST
    assert created.is_vet is False
    assert created.check_password("secret-pass")


@pytest.mark.django_db
def test_non_admin_cannot_manage_users():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    receptionist = User.objects.create_user(
        username="reception1",
        password="pass",
        clinic=clinic,
        role=User.Role.RECEPTIONIST,
    )
    client = APIClient()
    client.force_authenticate(user=receptionist)

    resp = client.get(reverse("users-list"))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_clinic_admin_lists_only_own_clinic_users():
    clinic1 = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    clinic2 = Clinic.objects.create(name="C2", address="a2", phone="p2", email="e2@e.com")
    admin = User.objects.create_user(
        username="admin1",
        password="pass",
        clinic=clinic1,
        is_staff=True,
        role=User.Role.ADMIN,
    )
    User.objects.create_user(
        username="doctor1",
        password="pass",
        clinic=clinic1,
        is_staff=True,
        is_vet=True,
        role=User.Role.DOCTOR,
    )
    User.objects.create_user(
        username="doctor_other",
        password="pass",
        clinic=clinic2,
        is_staff=True,
        is_vet=True,
        role=User.Role.DOCTOR,
    )
    client = APIClient()
    client.force_authenticate(user=admin)

    resp = client.get(reverse("users-list"))
    assert resp.status_code == 200
    usernames = {row["username"] for row in resp.data}
    assert "admin1" in usernames
    assert "doctor1" in usernames
    assert "doctor_other" not in usernames


@pytest.mark.django_db
def test_updating_role_keeps_is_vet_in_sync():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    admin = User.objects.create_user(
        username="admin1",
        password="pass",
        clinic=clinic,
        is_staff=True,
        role=User.Role.ADMIN,
    )
    user = User.objects.create_user(
        username="staff1",
        password="pass",
        clinic=clinic,
        is_staff=True,
        role=User.Role.RECEPTIONIST,
        is_vet=False,
    )
    client = APIClient()
    client.force_authenticate(user=admin)

    resp = client.patch(
        reverse("users-detail", args=[user.id]),
        {"role": User.Role.DOCTOR},
        format="json",
    )
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.role == User.Role.DOCTOR
    assert user.is_vet is True


@pytest.mark.django_db
def test_admin_cannot_remove_own_admin_role():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    admin = User.objects.create_user(
        username="admin1",
        password="pass",
        clinic=clinic,
        is_staff=True,
        role=User.Role.ADMIN,
    )
    client = APIClient()
    client.force_authenticate(user=admin)

    resp = client.patch(
        reverse("users-detail", args=[admin.id]),
        {"role": User.Role.RECEPTIONIST},
        format="json",
    )
    assert resp.status_code == 400
