"""
Create a test user, client, and patient for local/testing use.
Usage: python manage.py create_me_user

Login: username=me, password=me123
Use the returned patient ID for document upload: POST /api/documents/upload/ with patient=<id>
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.clients.models import Client, ClientClinic
from apps.patients.models import Patient
from apps.tenancy.models import Clinic


class Command(BaseCommand):
    help = "Creates a test user (me/me123), a client, and a patient for document upload testing."

    def handle(self, *args, **options):
        clinic = Clinic.objects.first()
        if not clinic:
            clinic = Clinic.objects.create(
                name="Test Clinic",
                address="123 Test St",
                phone="+1234567890",
                email="test@clinic.com",
            )
            self.stdout.write(self.style.SUCCESS(f"Created clinic: {clinic.name}"))
        else:
            self.stdout.write(f"Using clinic: {clinic.name}")

        user, user_created = User.objects.get_or_create(
            username="me",
            defaults={
                "first_name": "Me",
                "last_name": "Tester",
                "email": "me@test.com",
                "clinic": clinic,
                "is_vet": True,
                "role": User.Role.DOCTOR,
                "is_staff": True,
            },
        )
        if user_created:
            user.set_password("me123")
            user.save()
            self.stdout.write(self.style.SUCCESS("Created user: username=me, password=me123"))
        else:
            user.set_password("me123")
            user.save()
            self.stdout.write("User 'me' already exists; password reset to me123")

        client, client_created = Client.objects.get_or_create(
            email="me.client@test.com",
            defaults={
                "first_name": "Me",
                "last_name": "Client",
                "phone": "+1234567890",
            },
        )
        if client_created:
            self.stdout.write(self.style.SUCCESS(f"Created client: {client}"))
        else:
            self.stdout.write(f"Client already exists: {client}")

        ClientClinic.objects.get_or_create(
            client=client,
            clinic=clinic,
            defaults={"is_active": True},
        )

        patient, patient_created = Patient.objects.get_or_create(
            clinic=clinic,
            owner=client,
            name="Test Pet",
            defaults={
                "species": "Dog",
                "breed": "Mixed",
                "primary_vet": user,
            },
        )
        if patient_created:
            self.stdout.write(self.style.SUCCESS(f"Created patient: {patient} (id={patient.id})"))
        else:
            self.stdout.write(f"Patient already exists: {patient} (id={patient.id})")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("You can now:"))
        self.stdout.write("  1. Login: POST /api/auth/token/ with username=me, password=me123")
        self.stdout.write(
            f"  2. Upload a document: POST /api/documents/upload/ with file=@your.pdf, patient={patient.id}"
        )
