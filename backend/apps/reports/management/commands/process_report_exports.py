from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.reports.models import ReportExportJob
from apps.reports.services import build_report_csv


class Command(BaseCommand):
    help = "Process pending report export jobs."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--clinic-id", type=int, default=0)

    def handle(self, *args, **options):
        limit = max(1, min(1000, int(options.get("limit") or 100)))
        clinic_id = int(options.get("clinic_id") or 0)

        qs = ReportExportJob.objects.filter(status=ReportExportJob.Status.PENDING).order_by(
            "created_at", "id"
        )
        if clinic_id:
            qs = qs.filter(clinic_id=clinic_id)
        jobs = list(qs[:limit])
        processed = 0
        failed = 0

        for job in jobs:
            job.status = ReportExportJob.Status.PROCESSING
            job.error = ""
            job.save(update_fields=["status", "error", "updated_at"])
            try:
                file_name, content = build_report_csv(job)
                job.file_name = file_name
                job.file_content = content
                job.status = ReportExportJob.Status.COMPLETED
                job.completed_at = timezone.now()
                job.save(
                    update_fields=[
                        "file_name",
                        "file_content",
                        "status",
                        "completed_at",
                        "updated_at",
                    ]
                )
                processed += 1
            except Exception as exc:
                job.status = ReportExportJob.Status.FAILED
                job.error = str(exc)
                job.save(update_fields=["status", "error", "updated_at"])
                failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed: {processed}, Failed: {failed}, Total scanned: {len(jobs)}"
            )
        )
