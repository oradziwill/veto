import pytest

from apps.accounts.models import User
from apps.tenancy.models import Clinic


@pytest.mark.django_db
def test_me_requires_authentication(api_client):
    response = api_client.get("/api/me/")
    assert response.status_code == 401
    assert response.data["code"] == "not_authenticated"


@pytest.mark.django_db
def test_me_returns_authenticated_user(api_client, doctor):
    api_client.force_authenticate(user=doctor)
    response = api_client.get("/api/me/")
    assert response.status_code == 200
    assert response.data["id"] == doctor.id
    assert response.data["clinic"] == doctor.clinic_id
    assert response.data["role"] == User.Role.DOCTOR


@pytest.mark.django_db
def test_vets_list_is_clinic_scoped(api_client, doctor):
    other_clinic = Clinic.objects.create(
        name="Other Clinic",
        address="Street 2",
        phone="+48111222333",
        email="other@example.com",
    )
    other_vet = User.objects.create_user(
        username="other-vet",
        password="pass",
        clinic=other_clinic,
        role=User.Role.DOCTOR,
        is_vet=True,
    )
    User.objects.create_user(
        username="local-reception",
        password="pass",
        clinic=doctor.clinic,
        role=User.Role.RECEPTIONIST,
        is_vet=False,
    )

    api_client.force_authenticate(user=doctor)
    response = api_client.get("/api/vets/")
    assert response.status_code == 200
    ids = {row["id"] for row in response.data}
    assert doctor.id in ids
    assert other_vet.id not in ids


@pytest.mark.django_db
def test_jwt_token_lifecycle_obtain_and_refresh(api_client, receptionist):
    obtain = api_client.post(
        "/api/auth/token/",
        {"username": receptionist.username, "password": "pass"},
        format="json",
    )
    assert obtain.status_code == 200
    assert "access" in obtain.data
    assert "refresh" in obtain.data

    refresh = api_client.post(
        "/api/auth/token/refresh/",
        {"refresh": obtain.data["refresh"]},
        format="json",
    )
    assert refresh.status_code == 200
    assert "access" in refresh.data


@pytest.mark.django_db
def test_jwt_token_obtain_invalid_credentials(api_client, clinic):
    User.objects.create_user(
        username="token-user",
        password="pass",
        clinic=clinic,
        role=User.Role.RECEPTIONIST,
    )
    response = api_client.post(
        "/api/auth/token/",
        {"username": "token-user", "password": "wrong-pass"},
        format="json",
    )
    assert response.status_code == 401
    assert response.data["code"] == "authentication_failed"


@pytest.mark.django_db
def test_me_includes_network_for_network_admin(api_client):
    from apps.tenancy.models import ClinicNetwork

    net = ClinicNetwork.objects.create(name="Chain")
    u = User.objects.create_user(
        username="na-me",
        password="pass",
        role=User.Role.NETWORK_ADMIN,
        network=net,
        is_staff=True,
    )
    api_client.force_authenticate(user=u)
    response = api_client.get("/api/me/")
    assert response.status_code == 200
    assert response.data["network"] == net.id
    assert response.data["role"] == User.Role.NETWORK_ADMIN
