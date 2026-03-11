"""
Seed only the billing services catalog.
Usage: python manage.py seed_services

Use this when you need services for visits/invoicing but full seed_data fails
(e.g. on inventory or labs).
"""

from django.core.management.base import BaseCommand

from apps.billing.models import Service
from apps.tenancy.models import Clinic


class Command(BaseCommand):
    help = "Seeds only the billing services catalog"

    def handle(self, *args, **options):
        self.stdout.write("Seeding services catalog...")

        clinic = Clinic.objects.first()
        if not clinic:
            self.stdout.write(self.style.ERROR("No clinic found. Run seed_data first."))
            return

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

        self.stdout.write(self.style.SUCCESS("\n✓ Services seeding completed!"))
