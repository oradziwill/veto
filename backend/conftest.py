"""
Shared pytest fixtures for VETO backend tests.
"""

import pytest
from apps.accounts.models import User
from apps.billing.models import Service
from apps.clients.models import Client, ClientClinic
from apps.inventory.models import InventoryItem
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.tenancy.models import Clinic
from django.utils import timezone


@pytest.fixture
def clinic():
    """A clinic for tests."""
    return Clinic.objects.create(
        name="Test Clinic",
        address="123 Test St",
        phone="+1234567890",
        email="test@clinic.com",
    )


@pytest.fixture
def doctor(clinic):
    """A doctor (vet) user."""
    user = User.objects.create_user(
        username="doctor",
        password="pass",
        clinic=clinic,
        is_vet=True,
        is_staff=True,
        role=User.Role.DOCTOR,
    )
    return user


@pytest.fixture
def receptionist(clinic):
    """A receptionist user."""
    return User.objects.create_user(
        username="receptionist",
        password="pass",
        clinic=clinic,
        role=User.Role.RECEPTIONIST,
    )


@pytest.fixture
def clinic_admin(clinic):
    """A clinic admin user."""
    return User.objects.create_user(
        username="admin",
        password="pass",
        clinic=clinic,
        is_staff=True,
        role=User.Role.ADMIN,
    )


@pytest.fixture
def client():
    """A client (pet owner)."""
    return Client.objects.create(
        first_name="John",
        last_name="Doe",
        phone="+1234567890",
        email="john.doe@test.com",
    )


@pytest.fixture
def client_with_membership(client, clinic):
    """Client linked to clinic."""
    ClientClinic.objects.create(client=client, clinic=clinic, is_active=True)
    return client


@pytest.fixture
def patient(clinic, client_with_membership, doctor):
    """A patient (pet) linked to client."""
    return Patient.objects.create(
        clinic=clinic,
        owner=client_with_membership,
        name="Max",
        species="Dog",
        breed="Labrador",
        primary_vet=doctor,
    )


@pytest.fixture
def appointment(clinic, patient, doctor):
    """A scheduled appointment."""
    today = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
    return Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=today,
        ends_at=today.replace(minute=30),
        status=Appointment.Status.SCHEDULED,
        reason="Checkup",
    )


@pytest.fixture
def service(clinic):
    """A billable service."""
    return Service.objects.create(
        clinic=clinic,
        name="Consultation",
        code="CONS",
        price=150,
    )


@pytest.fixture
def inventory_item(clinic, doctor):
    """An inventory item."""
    return InventoryItem.objects.create(
        clinic=clinic,
        name="Test Medication",
        sku="TEST_MED",
        category=InventoryItem.Category.MEDICATION,
        unit="vials",
        stock_on_hand=100,
        low_stock_threshold=10,
        created_by=doctor,
    )


@pytest.fixture
def api_client():
    """REST framework API client."""
    from rest_framework.test import APIClient

    return APIClient()
