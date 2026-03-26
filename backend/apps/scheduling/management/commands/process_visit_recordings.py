from __future__ import annotations

import logging
from datetime import timedelta

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.scheduling.models import VisitRecording
from apps.scheduling.services.visit_recording_pipeline import (
    get_recordings_bucket,
    process_visit_recording,
    safe_error_text,
)

logger = logging.getLogger(__name__)


def get_s3_client():
    region = getattr(settings, "VISIT_RECORDINGS_S3_REGION", "") or getattr(
        settings, "DOCUMENTS_S3_REGION", "us-east-1"
    )
    return boto3.client("s3", region_name=region)


class Command(BaseCommand):
    help = "Process uploaded visit recordings and produce AI visit summaries."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--max-age-hours", type=int, default=72)
        parser.add_argument("--recording-id", type=int, default=None)

    def handle(self, *args, **options):
        bucket = get_recordings_bucket()
        if not bucket:
            self.stderr.write(
                "VISIT_RECORDINGS_S3_BUCKET (or DOCUMENTS_DATA_S3_BUCKET) is not set."
            )
            return

        limit = options["limit"]
        max_age_hours = options["max_age_hours"]
        recording_id = options["recording_id"]
        cutoff = timezone.now() - timedelta(hours=max_age_hours)

        if recording_id is not None:
            recordings = list(VisitRecording.objects.filter(pk=recording_id))
            if not recordings:
                self.stderr.write(self.style.WARNING(f"No VisitRecording with id={recording_id}."))
                return
        else:
            recordings = list(
                VisitRecording.objects.filter(
                    status=VisitRecording.Status.UPLOADED,
                    created_at__gte=cutoff,
                ).order_by("created_at")[:limit]
            )
            if not recordings:
                self.stdout.write("No visit recordings to process.")
                return

        client = get_s3_client()
        ready = 0
        failed = 0

        for recording in recordings:
            claimed = VisitRecording.objects.filter(
                pk=recording.pk,
                status=VisitRecording.Status.UPLOADED,
            ).update(status=VisitRecording.Status.PROCESSING, updated_at=timezone.now())
            if claimed == 0:
                continue
            recording.refresh_from_db()

            try:
                resp = client.get_object(Bucket=bucket, Key=recording.input_s3_key)
                audio_bytes = resp["Body"].read()
            except ClientError as exc:
                err = exc.response.get("Error") or {}
                msg = f"S3 download failed ({err.get('Code', 'ClientError')}): {err.get('Message', str(exc))}"
                logger.exception(
                    "Failed to download visit recording id=%s key=%s",
                    recording.id,
                    recording.input_s3_key,
                )
                recording.status = VisitRecording.Status.FAILED
                recording.last_error = safe_error_text(Exception(msg))
                recording.save(update_fields=["status", "last_error", "updated_at"])
                failed += 1
                continue
            except Exception as exc:
                logger.exception("Failed to download visit recording id=%s", recording.id)
                recording.status = VisitRecording.Status.FAILED
                recording.last_error = safe_error_text(exc)
                recording.save(update_fields=["status", "last_error", "updated_at"])
                failed += 1
                continue

            try:
                process_visit_recording(recording=recording, audio_bytes=audio_bytes)
            except Exception as exc:
                logger.exception("Visit recording processing failed id=%s", recording.id)
                recording.refresh_from_db()
                recording.status = VisitRecording.Status.FAILED
                recording.last_error = safe_error_text(exc)
                recording.save(update_fields=["status", "last_error", "updated_at"])
                failed += 1
                continue

            ready += 1
            self.stdout.write(
                f"Processed visit recording id={recording.id} appointment={recording.appointment_id}"
            )

        self.stdout.write(self.style.SUCCESS(f"Done: {ready} ready, {failed} failed."))
