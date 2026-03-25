"""Tests for release_stuck_document_processing management command."""

import io
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from django.core.management import call_command
from django.utils import timezone

from apps.documents.models import IngestionDocument


@pytest.mark.django_db
def test_release_stuck_dry_run_does_not_change_rows(clinic, patient, doctor, settings):
    doc = IngestionDocument.objects.create(
        clinic=clinic,
        patient=patient,
        original_filename="a.pdf",
        status=IngestionDocument.Status.PROCESSING,
        input_s3_key="documents_data/x/a.pdf",
        uploaded_by=doctor,
    )
    IngestionDocument.objects.filter(pk=doc.pk).update(
        updated_at=timezone.now() - timedelta(hours=2)
    )

    out = io.StringIO()
    call_command("release_stuck_document_processing", "--max-age-minutes=60", stdout=out)

    doc.refresh_from_db()
    assert doc.status == IngestionDocument.Status.PROCESSING
    assert "Dry-run only" in out.getvalue()


@pytest.mark.django_db
def test_release_stuck_apply_resets_to_uploaded(clinic, patient, doctor, settings):
    doc = IngestionDocument.objects.create(
        clinic=clinic,
        patient=patient,
        original_filename="a.pdf",
        status=IngestionDocument.Status.PROCESSING,
        input_s3_key="documents_data/x/a.pdf",
        uploaded_by=doctor,
    )
    IngestionDocument.objects.filter(pk=doc.pk).update(
        updated_at=timezone.now() - timedelta(hours=2)
    )

    out = io.StringIO()
    call_command(
        "release_stuck_document_processing",
        "--max-age-minutes=60",
        "--apply",
        stdout=out,
    )

    doc.refresh_from_db()
    assert doc.status == IngestionDocument.Status.UPLOADED
    assert doc.last_error == ""
    assert "Updated 1 row" in out.getvalue()


@pytest.mark.django_db
def test_release_stuck_apply_to_failed(clinic, patient, doctor, settings):
    doc = IngestionDocument.objects.create(
        clinic=clinic,
        patient=patient,
        original_filename="a.pdf",
        status=IngestionDocument.Status.PROCESSING,
        input_s3_key="documents_data/x/a.pdf",
        uploaded_by=doctor,
    )
    IngestionDocument.objects.filter(pk=doc.pk).update(
        updated_at=timezone.now() - timedelta(hours=2)
    )

    call_command(
        "release_stuck_document_processing",
        "--max-age-minutes=60",
        "--apply",
        "--to-failed",
    )

    doc.refresh_from_db()
    assert doc.status == IngestionDocument.Status.FAILED
    assert "release_stuck_document_processing" in doc.last_error


@pytest.mark.django_db
def test_release_stuck_ignores_recent_processing(clinic, patient, doctor, settings):
    IngestionDocument.objects.create(
        clinic=clinic,
        patient=patient,
        original_filename="a.pdf",
        status=IngestionDocument.Status.PROCESSING,
        input_s3_key="documents_data/x/a.pdf",
        uploaded_by=doctor,
    )

    out = io.StringIO()
    call_command("release_stuck_document_processing", "--max-age-minutes=60", stdout=out)
    assert "No stuck" in out.getvalue()


@pytest.mark.django_db
def test_process_document_ingestion_doc_id(clinic, patient, doctor, settings):
    settings.DOCUMENTS_DATA_S3_BUCKET = "test-bucket"
    settings.DOCUMENTS_S3_REGION = "us-east-1"
    doc = IngestionDocument.objects.create(
        clinic=clinic,
        patient=patient,
        original_filename="sample.pdf",
        content_type="application/pdf",
        status=IngestionDocument.Status.UPLOADED,
        uploaded_by=doctor,
    )
    doc.input_s3_key = f"documents_data/{doc.job_id}/sample.pdf"
    doc.save(update_fields=["input_s3_key"])

    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": io.BytesIO(b"%PDF-1.4 minimal content")}

    with patch(
        "apps.documents.management.commands.process_document_ingestion.get_s3_client",
        return_value=mock_s3,
    ):
        with patch(
            "apps.documents.management.commands.process_document_ingestion.convert_document_to_html",
            return_value="<html><body>x</body></html>",
        ):
            call_command("process_document_ingestion", f"--doc-id={doc.id}")

    doc.refresh_from_db()
    assert doc.status == IngestionDocument.Status.READY
    assert doc.last_error == ""


@pytest.mark.django_db
def test_process_document_ingestion_sets_last_error_on_client_error(
    clinic, patient, doctor, settings
):
    settings.DOCUMENTS_DATA_S3_BUCKET = "test-bucket"
    settings.DOCUMENTS_S3_REGION = "us-east-1"
    doc = IngestionDocument.objects.create(
        clinic=clinic,
        patient=patient,
        original_filename="sample.pdf",
        content_type="application/pdf",
        status=IngestionDocument.Status.UPLOADED,
        uploaded_by=doctor,
    )
    doc.input_s3_key = f"documents_data/{doc.job_id}/sample.pdf"
    doc.save(update_fields=["input_s3_key"])

    mock_s3 = MagicMock()
    mock_s3.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "missing"}},
        "GetObject",
    )

    with patch(
        "apps.documents.management.commands.process_document_ingestion.get_s3_client",
        return_value=mock_s3,
    ):
        call_command("process_document_ingestion", f"--doc-id={doc.id}")

    doc.refresh_from_db()
    assert doc.status == IngestionDocument.Status.FAILED
    assert "NoSuchKey" in doc.last_error
    assert "missing" in doc.last_error


@pytest.mark.django_db
def test_process_document_ingestion_clears_last_error_on_success(clinic, patient, doctor, settings):
    settings.DOCUMENTS_DATA_S3_BUCKET = "test-bucket"
    settings.DOCUMENTS_S3_REGION = "us-east-1"
    doc = IngestionDocument.objects.create(
        clinic=clinic,
        patient=patient,
        original_filename="sample.pdf",
        content_type="application/pdf",
        status=IngestionDocument.Status.UPLOADED,
        uploaded_by=doctor,
        last_error="previous",
    )
    doc.input_s3_key = f"documents_data/{doc.job_id}/sample.pdf"
    doc.save(update_fields=["input_s3_key"])

    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": io.BytesIO(b"%PDF")}

    with patch(
        "apps.documents.management.commands.process_document_ingestion.get_s3_client",
        return_value=mock_s3,
    ):
        with patch(
            "apps.documents.management.commands.process_document_ingestion.convert_document_to_html",
            return_value="<html><body>x</body></html>",
        ):
            call_command("process_document_ingestion", f"--doc-id={doc.id}")

    doc.refresh_from_db()
    assert doc.status == IngestionDocument.Status.READY
    assert doc.last_error == ""
