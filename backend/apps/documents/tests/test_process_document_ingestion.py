"""Tests for process_document_ingestion management command."""

import io
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command

from apps.documents.models import IngestionDocument


@pytest.mark.django_db
def test_process_document_ingestion_sets_ready(clinic, patient, doctor, settings):
    """Command processes one uploaded document and sets output_html_s3_key and status=ready."""
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
    put_calls = []

    def capture_put(**kwargs):
        put_calls.append(kwargs)

    mock_s3.put_object.side_effect = capture_put

    with patch(
        "apps.documents.management.commands.process_document_ingestion.get_s3_client",
        return_value=mock_s3,
    ):
        with patch(
            "apps.documents.management.commands.process_document_ingestion.convert_document_to_html",
            return_value="<html><body><p>test</p></body></html>",
        ):
            out = io.StringIO()
            call_command("process_document_ingestion", "--limit=5", stdout=out)

    doc.refresh_from_db()
    assert doc.status == IngestionDocument.Status.READY
    assert doc.output_html_s3_key.startswith(f"documents_data/{doc.job_id}/")
    assert doc.output_html_s3_key.endswith(".html")
    assert len(put_calls) == 1
    assert put_calls[0]["Key"] == doc.output_html_s3_key
    assert b"<html>" in put_calls[0]["Body"]


@pytest.mark.django_db
def test_process_document_ingestion_no_bucket(settings):
    """Command exits without error when DOCUMENTS_DATA_S3_BUCKET is not set."""
    settings.DOCUMENTS_DATA_S3_BUCKET = ""
    err = io.StringIO()
    call_command("process_document_ingestion", stderr=err)
    assert "not set" in err.getvalue()


@pytest.mark.django_db
def test_process_document_ingestion_nothing_to_process(clinic, patient, settings):
    """Command runs when no uploaded documents exist."""
    settings.DOCUMENTS_DATA_S3_BUCKET = "test-bucket"
    mock_s3 = MagicMock()
    with patch(
        "apps.documents.management.commands.process_document_ingestion.get_s3_client",
        return_value=mock_s3,
    ):
        out = io.StringIO()
        call_command("process_document_ingestion", stdout=out)
    assert "No documents" in out.getvalue()
    mock_s3.get_object.assert_not_called()
