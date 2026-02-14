"""
Management command to seed the database with initial data.
Usage: python manage.py seed_data
"""

from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.models import Service
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

        # Create Doctor
        vet, created = User.objects.get_or_create(
            username="drsmith",
            defaults={
                "first_name": "John",
                "last_name": "Smith",
                "email": "dr.smith@vetoclinic.com",
                "clinic": clinic,
                "is_vet": True,
                "role": User.Role.DOCTOR,
                "is_staff": True,
            },
        )
        if created:
            vet.set_password("password123")
            vet.save()
            self.stdout.write(self.style.SUCCESS(f"✓ Created doctor user: {vet.username}"))
        else:
            self.stdout.write(f"→ Doctor user already exists: {vet.username}")

        # Create Receptionist
        receptionist, created = User.objects.get_or_create(
            username="receptionist",
            defaults={
                "first_name": "Anna",
                "last_name": "Kowalska",
                "email": "anna@vetoclinic.com",
                "clinic": clinic,
                "is_vet": False,
                "role": User.Role.RECEPTIONIST,
                "is_staff": False,
            },
        )
        if created:
            receptionist.set_password("password123")
            receptionist.save()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Created receptionist user: {receptionist.username}")
            )
        else:
            self.stdout.write(f"→ Receptionist user already exists: {receptionist.username}")

        # Create Clinic Admin
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "first_name": "Maria",
                "last_name": "Director",
                "email": "admin@vetoclinic.com",
                "clinic": clinic,
                "is_vet": False,
                "role": User.Role.ADMIN,
                "is_staff": True,
            },
        )
        if created:
            admin_user.set_password("password123")
            admin_user.save()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Created clinic admin user: {admin_user.username}")
            )
        else:
            self.stdout.write(f"→ Clinic admin user already exists: {admin_user.username}")

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

        created_clients: list[Client] = []
        for client_data in clients_data:
            client, created = Client.objects.get_or_create(
                email=client_data["email"], defaults=client_data
            )
            created_clients.append(client)
            if created:
                self.stdout.write(self.style.SUCCESS(f"✓ Created client: {client}"))
            else:
                self.stdout.write(f"→ Client already exists: {client}")

        # Link clients to clinic
        for client in created_clients:
            ClientClinic.objects.get_or_create(
                client=client,
                clinic=clinic,
                defaults={"is_active": True},
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

        created_patients: list[Patient] = []
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
            created_patients.append(patient)
            if created:
                self.stdout.write(self.style.SUCCESS(f"✓ Created patient: {patient}"))
            else:
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
        #
        # IMPORTANT:
        # - Category choices are: medication, supply, food, other
        # - Fields were renamed:
        #   * stock_quantity -> stock_on_hand
        #   * min_stock_level -> low_stock_threshold
        #
        # If your InventoryItem has required fields like `created_by` or `sku`,
        # ensure they are provided below.
        inventory_data = [
            {
                "name": "Antibiotic A",
                "category": InventoryItem.Category.MEDICATION,
                "stock_on_hand": 150,
                "unit": "vials",
                "low_stock_threshold": 50,
            },
            {
                "name": "Surgical Gloves",
                "category": InventoryItem.Category.SUPPLY,
                "stock_on_hand": 25,
                "unit": "boxes",
                "low_stock_threshold": 30,
            },
            {
                "name": "X-Ray Film",
                "category": InventoryItem.Category.SUPPLY,
                "stock_on_hand": 0,
                "unit": "packs",
                "low_stock_threshold": 10,
            },
            {
                "name": "Vaccine B",
                "category": InventoryItem.Category.MEDICATION,
                "stock_on_hand": 80,
                "unit": "doses",
                "low_stock_threshold": 50,
            },
        ]

        for inv_data in inventory_data:
            # If created_by exists and is non-nullable, set it.
            if "created_by" in {f.name for f in InventoryItem._meta.get_fields()}:
                inv_data["created_by"] = vet

            # If sku exists, generate a stable seed SKU (and use it for idempotency).
            has_sku = "sku" in {f.name for f in InventoryItem._meta.get_fields()}
            if has_sku:
                sku = inv_data["name"].upper().replace(" ", "_").replace("-", "_")
                inv_data["sku"] = sku
                item, created = InventoryItem.objects.get_or_create(
                    clinic=clinic,
                    sku=sku,
                    defaults=inv_data,
                )
            else:
                item, created = InventoryItem.objects.get_or_create(
                    clinic=clinic,
                    name=inv_data["name"],
                    defaults=inv_data,
                )

            if created:
                self.stdout.write(self.style.SUCCESS(f"✓ Created inventory item: {item}"))
            else:
                self.stdout.write(f"→ Inventory item already exists: {item}")

        # Create Billing Services
        services_data = [
            {"name": "Consultation", "code": "CONS", "price": "150.00"},
            {"name": "Vaccination", "code": "VACC", "price": "80.00"},
            {"name": "Routine Checkup", "code": "CHECK", "price": "120.00"},
            {"name": "Blood Test", "code": "BLOOD", "price": "200.00"},
            {"name": "X-Ray", "code": "XRAY", "price": "250.00"},
        ]
        for svc_data in services_data:
            svc, created = Service.objects.get_or_create(
                clinic=clinic,
                code=svc_data["code"],
                defaults={
                    "name": svc_data["name"],
                    "price": svc_data["price"],
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"✓ Created service: {svc.name}"))
            else:
                self.stdout.write(f"→ Service already exists: {svc.name}")

        self.stdout.write(self.style.SUCCESS("\n✓ Database seeding completed!"))
        self.stdout.write("\nYou can now login with (password: password123):")
        self.stdout.write("  Doctor:       drsmith")
        self.stdout.write("  Receptionist: receptionist")
        self.stdout.write("  Clinic Admin: admin")
