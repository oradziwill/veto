"""
Management command to create sample doctor accounts for testing the scheduler.

Usage:
    docker compose exec backend python manage.py create_sample_doctors
    docker compose exec backend python manage.py create_sample_doctors --clinic-slug my-clinic
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()

SAMPLE_DOCTORS = [
    {
        "username": "dr_kowalski",
        "first_name": "Marek",
        "last_name": "Kowalski",
        "email": "m.kowalski@veto.local",
    },
    {
        "username": "dr_nowak",
        "first_name": "Anna",
        "last_name": "Nowak",
        "email": "a.nowak@veto.local",
    },
    {
        "username": "dr_wisniewski",
        "first_name": "Piotr",
        "last_name": "Wiśniewski",
        "email": "p.wisniewski@veto.local",
    },
    {
        "username": "dr_wojcik",
        "first_name": "Katarzyna",
        "last_name": "Wójcik",
        "email": "k.wojcik@veto.local",
    },
]

DEFAULT_PASSWORD = "Veto1234!"


class Command(BaseCommand):
    help = "Creates sample doctor accounts for testing the scheduler."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clinic-slug",
            type=str,
            default=None,
            help="Slug of the clinic to assign doctors to. Defaults to the first clinic.",
        )
        parser.add_argument(
            "--password",
            type=str,
            default=DEFAULT_PASSWORD,
            help=f"Password for created accounts (default: {DEFAULT_PASSWORD})",
        )

    def handle(self, *args, **options):
        from apps.tenancy.models import Clinic

        slug = options["clinic_slug"]
        password = options["password"]

        try:
            clinic = Clinic.objects.get(slug=slug) if slug else Clinic.objects.first()
        except Clinic.DoesNotExist as e:
            raise CommandError(f"Clinic with slug '{slug}' not found.") from e

        if clinic is None:
            raise CommandError("No clinic found. Create a clinic first.")

        self.stdout.write(
            f"Creating sample doctors for clinic: {clinic.name} (slug: {clinic.slug})"
        )

        created_count = 0
        skipped_count = 0

        for data in SAMPLE_DOCTORS:
            if User.objects.filter(username=data["username"]).exists():
                self.stdout.write(
                    self.style.WARNING(f"  Skipping {data['username']} — already exists.")
                )
                skipped_count += 1
                continue

            user = User.objects.create_user(
                username=data["username"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                email=data["email"],
                password=password,
                role="doctor",
                is_vet=True,
                clinic=clinic,
            )
            created_count += 1
            self.stdout.write(
                self.style.SUCCESS(f"  Created: {user.get_full_name()} ({user.username})")
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Done. Created: {created_count}, Skipped: {skipped_count}")
        )
        if created_count > 0:
            self.stdout.write(f"Default password: {password}")
