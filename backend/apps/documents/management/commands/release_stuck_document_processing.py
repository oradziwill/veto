"""
Reset rows left in status=processing (e.g. worker crash). By default dry-run.

Usage:
  python manage.py release_stuck_document_processing --max-age-minutes 30
  python manage.py release_stuck_document_processing --max-age-minutes 30 --apply
  python manage.py release_stuck_document_processing --apply --to-failed
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.documents.models import IngestionDocument


class Command(BaseCommand):
    help = (
        "Find IngestionDocument rows stuck in processing (updated_at older than threshold). "
        "By default prints matches only; use --apply to reset to uploaded (retry) or --to-failed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-age-minutes",
            type=int,
            default=30,
            help="Rows must have updated_at older than this many minutes (default: 30).",
        )
        parser.add_argument("--limit", type=int, default=200)
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Perform updates (without this flag, dry-run only).",
        )
        parser.add_argument(
            "--to-failed",
            action="store_true",
            help="Set status=failed instead of uploaded (no automatic retry by batch processor).",
        )

    def handle(self, *args, **options):
        max_age = options["max_age_minutes"]
        limit = options["limit"]
        apply = options["apply"]
        to_failed = options["to_failed"]

        cutoff = timezone.now() - timedelta(minutes=max_age)
        qs = IngestionDocument.objects.filter(
            status=IngestionDocument.Status.PROCESSING,
            updated_at__lt=cutoff,
        ).order_by("updated_at")[:limit]
        docs = list(qs)
        if not docs:
            self.stdout.write("No stuck processing documents match the criteria.")
            return

        self.stdout.write(
            f"Found {len(docs)} document(s) in processing older than {max_age} minutes "
            f"(updated_at < {cutoff.isoformat()})."
        )
        for doc in docs:
            self.stdout.write(f"  id={doc.id} job_id={doc.job_id} updated_at={doc.updated_at}")

        if not apply:
            self.stdout.write(self.style.WARNING("Dry-run only. Pass --apply to update rows."))
            return

        fail_msg = (
            "Stuck in processing (marked failed by release_stuck_document_processing --to-failed)."
        )

        changed = 0
        for doc in docs:
            if to_failed:
                doc.status = IngestionDocument.Status.FAILED
                doc.last_error = fail_msg
            else:
                doc.status = IngestionDocument.Status.UPLOADED
                doc.last_error = ""
            doc.save(update_fields=["status", "last_error", "updated_at"])
            changed += 1

        action = "failed" if to_failed else "reset to uploaded"
        self.stdout.write(self.style.SUCCESS(f"Updated {changed} row(s) ({action})."))
