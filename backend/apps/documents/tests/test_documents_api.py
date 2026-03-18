"""Tests for document ingestion API: upload, list, retrieve, download-url."""

from unittest.mock import MagicMock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.documents.models import IngestionDocument


@pytest.mark.django_db
def test_upload_creates_row_and_s3_key(api_client, doctor, patient, settings):
    """Upload creates IngestionDocument with status=uploaded and input_s3_key; S3 put is called."""
    settings.DOCUMENTS_DATA_S3_BUCKET = "test-bucket"
    settings.DOCUMENTS_S3_REGION = "us-east-1"
    mock_s3 = MagicMock()
    with patch("apps.documents.views._get_s3_client", return_value=mock_s3):
        api_client.force_authenticate(user=doctor)
        pdf = SimpleUploadedFile(
            "report.pdf",
            b"%PDF-1.4 minimal",
            content_type="application/pdf",
        )
        data = {
            "file": pdf,
            "patient": patient.id,
        }
        r = api_client.post("/api/documents/upload/", data, format="multipart")
    assert r.status_code == 201
    payload = r.json()
    assert payload["status"] == "uploaded"
    assert "job_id" in payload
    assert payload["input_s3_key"].startswith("documents_data/")
    assert payload["input_s3_key"].endswith("report.pdf")
    assert IngestionDocument.objects.filter(id=payload["id"]).exists()
    doc = IngestionDocument.objects.get(id=payload["id"])
    assert doc.clinic_id == doctor.clinic_id
    assert doc.patient_id == patient.id
    assert doc.original_filename == "report.pdf"
    mock_s3.upload_fileobj.assert_called_once()


@pytest.mark.django_db
def test_upload_requires_patient(api_client, doctor, settings):
    """Upload without patient returns 400."""
    settings.DOCUMENTS_DATA_S3_BUCKET = "test-bucket"
    api_client.force_authenticate(user=doctor)
    pdf = SimpleUploadedFile("x.pdf", b"%PDF", content_type="application/pdf")
    r = api_client.post(
        "/api/documents/upload/",
        {"file": pdf},
        format="multipart",
    )
    assert r.status_code == 400


@pytest.mark.django_db
def test_list_clinic_scoped(api_client, doctor, patient):
    """List returns only documents for the user's clinic."""
    doc1 = IngestionDocument.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        original_filename="a.pdf",
        status=IngestionDocument.Status.READY,
        input_s3_key="documents_data/uu/a.pdf",
        output_html_s3_key="documents_data/uu/a.html",
    )
    api_client.force_authenticate(user=doctor)
    r = api_client.get("/api/documents/")
    assert r.status_code == 200
    results = r.json()["results"] if "results" in r.json() else r.json()
    ids = [x["id"] for x in results]
    assert doc1.id in ids


@pytest.mark.django_db
def test_list_filter_by_patient(api_client, doctor, patient, client_with_membership):
    """List can filter by patient."""
    from apps.patients.models import Patient

    patient2 = Patient.objects.create(
        clinic=doctor.clinic,
        owner=client_with_membership,
        name="SecondPet",
        species="Cat",
    )
    IngestionDocument.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        original_filename="p1.pdf",
        status=IngestionDocument.Status.UPLOADED,
        input_s3_key="documents_data/j1/p1.pdf",
    )
    doc2 = IngestionDocument.objects.create(
        clinic=doctor.clinic,
        patient=patient2,
        original_filename="p2.pdf",
        status=IngestionDocument.Status.UPLOADED,
        input_s3_key="documents_data/j2/p2.pdf",
    )
    api_client.force_authenticate(user=doctor)
    r = api_client.get(f"/api/documents/?patient={patient2.id}")
    assert r.status_code == 200
    results = r.json()["results"] if "results" in r.json() else r.json()
    assert len(results) == 1
    assert results[0]["id"] == doc2.id


@pytest.mark.django_db
def test_retrieve_returns_metadata(api_client, doctor, patient):
    """GET /api/documents/{id}/ returns document metadata."""
    doc = IngestionDocument.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        original_filename="retrieve.pdf",
        status=IngestionDocument.Status.READY,
        input_s3_key="documents_data/job/retrieve.pdf",
        output_html_s3_key="documents_data/job/retrieve.html",
    )
    api_client.force_authenticate(user=doctor)
    r = api_client.get(f"/api/documents/{doc.id}/")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == doc.id
    assert data["job_id"] == str(doc.job_id)
    assert data["status"] == "ready"
    assert data["output_html_s3_key"] == "documents_data/job/retrieve.html"


@pytest.mark.django_db
def test_download_url_returns_presigned(api_client, doctor, patient, settings):
    """POST /api/documents/{id}/download-url/ returns presigned URL."""
    settings.DOCUMENTS_DATA_S3_BUCKET = "test-bucket"
    doc = IngestionDocument.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        original_filename="out.pdf",
        status=IngestionDocument.Status.READY,
        input_s3_key="documents_data/j/out.pdf",
        output_html_s3_key="documents_data/j/out.html",
    )
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://s3.example.com/presigned"
    with patch("apps.documents.views._get_s3_client", return_value=mock_s3):
        api_client.force_authenticate(user=doctor)
        r = api_client.post(f"/api/documents/{doc.id}/download-url/")
    assert r.status_code == 200
    data = r.json()
    assert data["url"] == "https://s3.example.com/presigned"
    assert data["expires_in"] == 3600
    mock_s3.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "test-bucket", "Key": "documents_data/j/out.html"},
        ExpiresIn=3600,
    )
