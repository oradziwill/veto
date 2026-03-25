"""
Process documents with status=uploaded: download from S3, convert to HTML, upload HTML to S3, set status=ready/failed.
Usage: python manage.py process_document_ingestion [--limit N] [--max-age-hours H] [--doc-id ID]
"""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.documents.models import IngestionDocument
from apps.documents.services.conversion import convert_document_to_html

logger = logging.getLogger(__name__)

_LAST_ERROR_MAX = 10000


def get_s3_client():
    region = getattr(settings, "DOCUMENTS_S3_REGION", "us-east-1")
    return boto3.client("s3", region_name=region)


def _truncate_error(message: str) -> str:
    message = message.strip()
    if len(message) <= _LAST_ERROR_MAX:
        return message
    return message[: _LAST_ERROR_MAX - 20] + "\n…(truncated)"


class Command(BaseCommand):
    help = (
        "Process uploaded documents: download from S3, convert to HTML, upload HTML, update status."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--max-age-hours", type=int, default=72)
        parser.add_argument(
            "--doc-id",
            type=int,
            default=None,
            help="Process exactly this document id (must be status=uploaded).",
        )

    def handle(self, *args, **options):
        bucket = getattr(settings, "DOCUMENTS_DATA_S3_BUCKET", None)
        if not bucket:
            self.stderr.write("DOCUMENTS_DATA_S3_BUCKET is not set.")
            return

        limit = options["limit"]
        max_age_hours = options["max_age_hours"]
        doc_id = options["doc_id"]
        cutoff = timezone.now() - timedelta(hours=max_age_hours)

        if doc_id is not None:
            docs = list(IngestionDocument.objects.filter(pk=doc_id))
            if not docs:
                self.stderr.write(self.style.WARNING(f"No IngestionDocument with id={doc_id}."))
                return
        else:
            qs = IngestionDocument.objects.filter(
                status=IngestionDocument.Status.UPLOADED,
                created_at__gte=cutoff,
            ).order_by("created_at")[:limit]
            docs = list(qs)
            if not docs:
                self.stdout.write("No documents to process.")
                return

        client = get_s3_client()
        ready = 0
        failed = 0

        for doc in docs:
            claimed = IngestionDocument.objects.filter(
                pk=doc.pk,
                status=IngestionDocument.Status.UPLOADED,
            ).update(status=IngestionDocument.Status.PROCESSING, updated_at=timezone.now())
            if claimed == 0:
                doc.refresh_from_db()
                if doc_id is not None:
                    self.stderr.write(
                        self.style.WARNING(
                            f"Document id={doc_id} is not claimable (status={doc.status})."
                        )
                    )
                continue
            doc.refresh_from_db()

            try:
                resp = client.get_object(Bucket=bucket, Key=doc.input_s3_key)
                data = resp["Body"].read()
            except ClientError as exc:
                err = exc.response.get("Error") or {}
                code = err.get("Code", "ClientError")
                msg = err.get("Message", str(exc))
                message = _truncate_error(f"S3 download failed ({code}): {msg}")
                logger.exception(
                    "Failed to download document id=%s key=%s", doc.id, doc.input_s3_key
                )
                doc.status = IngestionDocument.Status.FAILED
                doc.last_error = message
                doc.save(update_fields=["status", "last_error", "updated_at"])
                failed += 1
                continue
            except Exception as exc:
                message = _truncate_error(f"Download failed: {exc!s}")
                logger.exception(
                    "Failed to download document id=%s key=%s", doc.id, doc.input_s3_key
                )
                doc.status = IngestionDocument.Status.FAILED
                doc.last_error = message
                doc.save(update_fields=["status", "last_error", "updated_at"])
                failed += 1
                continue

            try:
                html_content = convert_document_to_html(
                    data,
                    doc.content_type or "",
                    doc.original_filename or "",
                )
            except Exception as exc:
                message = _truncate_error(f"Conversion failed: {exc!s}")
                logger.exception("Conversion failed for document id=%s", doc.id)
                doc.status = IngestionDocument.Status.FAILED
                doc.last_error = message
                doc.save(update_fields=["status", "last_error", "updated_at"])
                failed += 1
                continue

            stem = Path(doc.original_filename or "file").stem
            safe_stem = "".join(c for c in stem if c.isalnum() or c in "-_")[:100] or "output"
            output_key = f"documents_data/{doc.job_id}/{safe_stem}.html"

            try:
                client.put_object(
                    Bucket=bucket,
                    Key=output_key,
                    Body=html_content.encode("utf-8"),
                    ContentType="text/html; charset=utf-8",
                )
            except Exception as exc:
                message = _truncate_error(f"S3 upload failed: {exc!s}")
                logger.exception("Failed to upload HTML for document id=%s", doc.id)
                doc.status = IngestionDocument.Status.FAILED
                doc.last_error = message
                doc.save(update_fields=["status", "last_error", "updated_at"])
                failed += 1
                continue

            doc.output_html_s3_key = output_key
            doc.status = IngestionDocument.Status.READY
            doc.last_error = ""
            doc.save(update_fields=["output_html_s3_key", "status", "last_error", "updated_at"])
            ready += 1
            self.stdout.write(f"Processed document id={doc.id} job_id={doc.job_id} -> {output_key}")

        self.stdout.write(self.style.SUCCESS(f"Done: {ready} ready, {failed} failed."))
