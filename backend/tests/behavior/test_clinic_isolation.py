"""
Behavior: Multi-clinic isolation.

Users from clinic A cannot access or modify data belonging to clinic B.
"""

import pytest
from apps.accounts.models import User
from apps.billing.models import Invoice
from apps.clients.models import Client, ClientClinic
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.tenancy.models import Clinic
from django.utils import timezone


@pytest.mark.django_db
class TestClinicIsolation:
    """Verify clinic-scoped data isolation."""

    def test_user_cannot_see_other_clinic_invoices(self, api_client):
        """Behavior: Invoice list returns only current user's clinic invoices."""
        c1 = Clinic.objects.create(name="Clinic 1", address="a", phone="p", email="e1@x.com")
        c2 = Clinic.objects.create(name="Clinic 2", address="b", phone="q", email="e2@x.com")

        user1 = User.objects.create_user(
            username="u1",
            password="pass",
            clinic=c1,
            role=User.Role.RECEPTIONIST,
        )
        client1 = Client.objects.create(first_name="A", last_name="B", email="a@x.com")
        ClientClinic.objects.create(client=client1, clinic=c1)
        Patient.objects.create(clinic=c1, owner=client1, name="P1", species="dog")

        # Invoice in clinic 2
        client2 = Client.objects.create(first_name="C", last_name="D", email="c@x.com")
        ClientClinic.objects.create(client=client2, clinic=c2)
        patient2 = Patient.objects.create(clinic=c2, owner=client2, name="P2", species="cat")
        inv2 = Invoice.objects.create(clinic=c2, client=client2, patient=patient2, status="draft")

        api_client.force_authenticate(user=user1)
        r = api_client.get("/api/billing/invoices/")
        assert r.status_code == 200
        ids = [x["id"] for x in r.data]
        assert inv2.id not in ids

    def test_user_cannot_retrieve_other_clinic_appointment(self, api_client):
        """Behavior: Appointment retrieve returns 404 for other clinic's appointment."""
        c1 = Clinic.objects.create(name="C1", address="a", phone="p", email="e1@x.com")
        c2 = Clinic.objects.create(name="C2", address="b", phone="q", email="e2@x.com")

        user1 = User.objects.create_user(
            username="u1",
            password="pass",
            clinic=c1,
            role=User.Role.DOCTOR,
        )
        vet2 = User.objects.create_user(
            username="v2",
            password="pass",
            clinic=c2,
            is_vet=True,
            role=User.Role.DOCTOR,
        )
        client2 = Client.objects.create(first_name="X", last_name="Y", email="x@x.com")
        ClientClinic.objects.create(client=client2, clinic=c2)
        patient2 = Patient.objects.create(clinic=c2, owner=client2, name="P", species="dog")

        today = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        appt2 = Appointment.objects.create(
            clinic=c2,
            patient=patient2,
            vet=vet2,
            starts_at=today,
            ends_at=today.replace(minute=30),
            status="scheduled",
        )

        api_client.force_authenticate(user=user1)
        r = api_client.get(f"/api/appointments/{appt2.id}/")
        assert r.status_code == 404
