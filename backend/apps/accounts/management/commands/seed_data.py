"""
Management command to seed the database with initial data.
Usage: python manage.py seed_data
"""

from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.clients.models import Client, ClientClinic
from apps.inventory.models import InventoryItem
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.tenancy.models import Clinic


class Command(BaseCommand):
    help = "Seeds the database with initial sample data"

    def handle(self, *args, **options):
        self.stdout.write("Starting to seed database...")

        # Create Clinic
        clinic, created = Clinic.objects.get_or_create(
            name="Veto Clinic",
            defaults={
                "address": "123 Veterinary Street, City, State 12345",
                "phone": "+1-555-0123",
                "email": "info@vetoclinic.com",
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"✓ Created clinic: {clinic.name}"))
        else:
            self.stdout.write(f"→ Clinic already exists: {clinic.name}")

        # Create Vet User
        vet, created = User.objects.get_or_create(
            username="drsmith",
            defaults={
                "first_name": "John",
                "last_name": "Smith",
                "email": "dr.smith@vetoclinic.com",
                "clinic": clinic,
                "is_vet": True,
                "is_staff": True,
            },
        )
        if created:
            vet.set_password("password123")
            vet.save()
            self.stdout.write(self.style.SUCCESS(f"✓ Created vet user: {vet.username}"))
        else:
            self.stdout.write(f"→ Vet user already exists: {vet.username}")

        # Create Clients
        clients_data = [
            {
                "first_name": "John",
                "last_name": "Doe",
                "phone": "+1-555-1001",
                "email": "john.doe@email.com",
            },
            {
                "first_name": "Jane",
                "last_name": "Smith",
                "phone": "+1-555-1002",
                "email": "jane.smith@email.com",
            },
            {
                "first_name": "Mike",
                "last_name": "Johnson",
                "phone": "+1-555-1003",
                "email": "mike.johnson@email.com",
            },
        ]

        created_clients = []
        for client_data in clients_data:
            client, created = Client.objects.get_or_create(
                email=client_data["email"], defaults=client_data
            )
            if created:
                created_clients.append(client)
                self.stdout.write(self.style.SUCCESS(f"✓ Created client: {client}"))
            else:
                created_clients.append(client)
                self.stdout.write(f"→ Client already exists: {client}")

        # Link clients to clinic
        for client in created_clients:
            ClientClinic.objects.get_or_create(
                client=client, clinic=clinic, defaults={"is_active": True}
            )

        # Create Patients
        patients_data = [
            {
                "name": "Max",
                "species": "Dog",
                "breed": "Golden Retriever",
                "sex": "Male",
                "birth_date": datetime(2019, 1, 15).date(),
                "owner": created_clients[0],
            },
            {
                "name": "Luna",
                "species": "Cat",
                "breed": "Persian",
                "sex": "Female",
                "birth_date": datetime(2021, 3, 20).date(),
                "owner": created_clients[1],
            },
            {
                "name": "Bunny",
                "species": "Rabbit",
                "breed": "Dutch",
                "sex": "Female",
                "birth_date": datetime(2022, 6, 10).date(),
                "owner": created_clients[2],
            },
        ]

        created_patients = []
        for patient_data in patients_data:
            patient, created = Patient.objects.get_or_create(
                clinic=clinic,
                name=patient_data["name"],
                owner=patient_data["owner"],
                defaults={
                    **{k: v for k, v in patient_data.items() if k != "owner"},
                    "primary_vet": vet,
                },
            )
            if created:
                created_patients.append(patient)
                self.stdout.write(self.style.SUCCESS(f"✓ Created patient: {patient}"))
            else:
                created_patients.append(patient)
                self.stdout.write(f"→ Patient already exists: {patient}")

        # Create Appointments
        now = timezone.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        appointments_data = [
            {
                "patient": created_patients[0],
                "vet": vet,
                "starts_at": today.replace(hour=10, minute=0),
                "ends_at": today.replace(hour=10, minute=30),
                "reason": "Routine Checkup",
                "status": Appointment.Status.SCHEDULED,
            },
            {
                "patient": created_patients[1],
                "vet": vet,
                "starts_at": today.replace(hour=11, minute=30),
                "ends_at": today.replace(hour=12, minute=0),
                "reason": "Vaccination",
                "status": Appointment.Status.SCHEDULED,
            },
            {
                "patient": created_patients[2],
                "vet": vet,
                "starts_at": today.replace(hour=14, minute=0),
                "ends_at": today.replace(hour=14, minute=30),
                "reason": "Follow-up",
                "status": Appointment.Status.COMPLETED,
            },
        ]

        for apt_data in appointments_data:
            appointment, created = Appointment.objects.get_or_create(
                clinic=clinic,
                patient=apt_data["patient"],
                vet=apt_data["vet"],
                starts_at=apt_data["starts_at"],
                defaults=apt_data,
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"✓ Created appointment: {appointment}"))
            else:
                self.stdout.write(f"→ Appointment already exists: {appointment}")

        # Create Inventory Items
        inventory_data = [
            {
                "name": "Antibiotic A",
                "category": InventoryItem.Category.MEDICATION,
                "stock_quantity": 150,
                "unit": "vials",
                "min_stock_level": 50,
            },
            {
                "name": "Surgical Gloves",
                "category": InventoryItem.Category.SUPPLIES,
                "stock_quantity": 25,
                "unit": "boxes",
                "min_stock_level": 30,
            },
            {
                "name": "X-Ray Film",
                "category": InventoryItem.Category.EQUIPMENT,
                "stock_quantity": 0,
                "unit": "packs",
                "min_stock_level": 10,
            },
            {
                "name": "Vaccine B",
                "category": InventoryItem.Category.MEDICATION,
                "stock_quantity": 80,
                "unit": "doses",
                "min_stock_level": 50,
            },
        ]

        for inv_data in inventory_data:
            item, created = InventoryItem.objects.get_or_create(
                clinic=clinic, name=inv_data["name"], defaults=inv_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"✓ Created inventory item: {item}"))
            else:
                self.stdout.write(f"→ Inventory item already exists: {item}")

        self.stdout.write(self.style.SUCCESS("\n✓ Database seeding completed!"))
        self.stdout.write("\nYou can now login with:")
        self.stdout.write("  Username: drsmith")
        self.stdout.write("  Password: password123")
