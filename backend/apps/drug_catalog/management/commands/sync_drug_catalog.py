from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.drug_catalog.models import SyncRun
from apps.drug_catalog.services import ema_upd
from apps.drug_catalog.services.sync import run_ema_sync


class Command(BaseCommand):
    help = (
        "Sync veterinary drug reference products from EMA UPD (when EMA_UPD_* env is configured). "
        "Without base URL / products path, completes with zero rows."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--incremental",
            action="store_true",
            help="Incremental mode (reserved for future delta sync).",
        )

    def handle(self, *args, **options):
        incremental = bool(options.get("incremental"))
        mode = SyncRun.Mode.INCREMENTAL if incremental else SyncRun.Mode.FULL

        run = SyncRun.objects.create(mode=mode, status=SyncRun.Status.STARTED)
        try:
            if not ema_upd.is_configured():
                run.status = SyncRun.Status.SUCCESS
                run.records_processed = 0
                run.detail = {"skipped": True, "reason": "EMA_UPD_BASE_URL not set"}
                self.stdout.write(
                    self.style.WARNING(
                        "EMA_UPD_BASE_URL not set — no remote sync. "
                        "Populate ReferenceProduct via admin or seed data."
                    )
                )
            else:
                n, detail = run_ema_sync(incremental=incremental)
                run.status = SyncRun.Status.SUCCESS
                run.records_processed = n
                run.detail = detail
                self.stdout.write(
                    self.style.SUCCESS(f"sync_drug_catalog: upserted {run.records_processed} rows")
                )
        except Exception as exc:
            run.status = SyncRun.Status.FAILED
            run.error_message = str(exc)[:8000]
            raise
        finally:
            run.finished_at = timezone.now()
            run.save(
                update_fields=[
                    "status",
                    "records_processed",
                    "error_message",
                    "detail",
                    "finished_at",
                ]
            )
