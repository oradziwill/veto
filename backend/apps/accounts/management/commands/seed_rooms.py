"""
Seed example rooms for existing clinics.
Usage: python manage.py seed_rooms

Run this to add Room 1, Room 2, RTG room, Surgery to the first clinic.
"""

from django.core.management.base import BaseCommand

from apps.scheduling.models import Room
from apps.tenancy.models import Clinic


class Command(BaseCommand):
    help = "Seeds example rooms for the first clinic"

    def handle(self, *args, **options):
        self.stdout.write("Seeding rooms...")

        clinic = Clinic.objects.first()
        if not clinic:
            self.stdout.write(self.style.ERROR("No clinic found. Run seed_data first."))
            return

        example_rooms = [
            ("Room 1", 0),
            ("Room 2", 1),
            ("RTG room", 2),
            ("Surgery", 3),
        ]
        for name, order in example_rooms:
            room, created = Room.objects.get_or_create(
                clinic=clinic,
                name=name,
                defaults={"display_order": order},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"✓ Created room: {room.name}"))
            else:
                room.display_order = order
                room.save(update_fields=["display_order"])
                self.stdout.write(f"→ Room already exists: {room.name}")

        self.stdout.write(self.style.SUCCESS("\n✓ Rooms seeding completed!"))
