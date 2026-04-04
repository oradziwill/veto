from django.core.management.base import BaseCommand

from apps.reports.job_runner import execute_report_export_job_by_id
from apps.reports.models import ReportExportJob


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
        skipped = 0

        for job in jobs:
            result = execute_report_export_job_by_id(job.id)
            if result == "processed":
                processed += 1
            elif result == "failed":
                failed += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed: {processed}, Failed: {failed}, Skipped: {skipped}, "
                f"Total scanned: {len(jobs)}"
            )
        )
