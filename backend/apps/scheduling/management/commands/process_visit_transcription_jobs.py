from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.scheduling.models import VisitTranscriptionJob
from apps.scheduling.services.visit_transcription_job import process_visit_transcription_job


class Command(BaseCommand):
    help = "Process pending visit transcription jobs (Whisper + clinical exam update)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--max-age-hours", type=int, default=72)
        parser.add_argument("--job-id", type=int, default=None)

    def handle(self, *args, **options):
        limit = options["limit"]
        max_age_hours = options["max_age_hours"]
        job_id = options["job_id"]
        cutoff = timezone.now() - timedelta(hours=max_age_hours)

        if job_id is not None:
            process_visit_transcription_job(job_id)
            self.stdout.write(self.style.SUCCESS(f"Processed job id={job_id} (if it was pending)."))
            return

        qs = VisitTranscriptionJob.objects.filter(
            status=VisitTranscriptionJob.Status.PENDING,
            created_at__gte=cutoff,
        ).order_by("created_at")[:limit]
        ids = list(qs.values_list("id", flat=True))
        if not ids:
            self.stdout.write("No pending visit transcription jobs.")
            return

        for jid in ids:
            process_visit_transcription_job(jid)

        self.stdout.write(self.style.SUCCESS(f"Processed {len(ids)} transcription job(s)."))
