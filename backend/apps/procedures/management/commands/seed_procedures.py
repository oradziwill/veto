"""
Seed the database with 8 clinical procedures.
Usage: python manage.py seed_procedures
"""

from __future__ import annotations

import json
import os

from django.core.management.base import BaseCommand

from apps.procedures.models import ClinicalProcedure


class Command(BaseCommand):
    help = "Load 8 clinical procedure fixtures"

    def handle(self, *args, **options):
        fixture_path = os.path.join(os.path.dirname(__file__), "../../fixtures/procedures.json")
        fixture_path = os.path.abspath(fixture_path)

        with open(fixture_path) as f:
            records = json.load(f)

        created = 0
        for record in records:
            fields = record["fields"]
            _, was_created = ClinicalProcedure.objects.update_or_create(
                slug=fields["slug"],
                defaults={
                    "name": fields["name"],
                    "name_en": fields.get("name_en", ""),
                    "category": fields["category"],
                    "species": fields["species"],
                    "entry_node_id": fields["entry_node_id"],
                    "nodes": fields["nodes"],
                    "tags": fields.get("tags", []),
                    "source": fields.get("source", ""),
                    "is_active": fields.get("is_active", True),
                },
            )
            if was_created:
                created += 1

        total = ClinicalProcedure.objects.count()
        self.stdout.write(self.style.SUCCESS(f"✓ {created} new procedures created. Total: {total}"))
