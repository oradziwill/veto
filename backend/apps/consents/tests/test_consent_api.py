"""Tests for consent document API."""

from unittest.mock import MagicMock, patch

import pytest
from apps.consents.models import ConsentDocument
from django.core.files.uploadedfile import SimpleUploadedFile

# Minimal valid 1x1 PNG
_MIN_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.django_db
def test_create_and_preview(api_client, doctor, appointment, settings):
    settings.DOCUMENTS_DATA_S3_BUCKET = "test-bucket"
    api_client.force_authenticate(user=doctor)
    r = api_client.post(
        "/api/consent-documents/",
        {"appointment": appointment.id, "location_label": "reception"},
        format="json",
    )
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "pending_signature"
    assert len(data["content_hash"]) == 64
    cid = data["id"]

    r2 = api_client.get(f"/api/consent-documents/{cid}/preview/")
    assert r2.status_code == 200
    assert r2["Content-Type"] == "application/pdf"
    assert r2.content[:4] == b"%PDF"


@pytest.mark.django_db
def test_sign_uploads_s3(api_client, doctor, appointment, settings):
    settings.DOCUMENTS_DATA_S3_BUCKET = "test-bucket"
    settings.DOCUMENTS_S3_REGION = "us-east-1"
    api_client.force_authenticate(user=doctor)
    r = api_client.post("/api/consent-documents/", {"appointment": appointment.id}, format="json")
    assert r.status_code == 201
    payload = r.json()
    cid = payload["id"]
    ch = payload["content_hash"]

    mock_s3 = MagicMock()
    with patch("apps.consents.views._get_s3_client", return_value=mock_s3):
        r2 = api_client.post(
            f"/api/consent-documents/{cid}/sign/",
            {
                "content_hash": ch,
                "signature": SimpleUploadedFile("sig.png", _MIN_PNG, content_type="image/png"),
            },
            format="multipart",
        )
    assert r2.status_code == 200, r2.content
    out = r2.json()
    assert out["status"] == "signed"
    assert out["signed_by"] == doctor.id
    doc = ConsentDocument.objects.get(id=cid)
    assert doc.final_pdf_s3_key.endswith("final.pdf")
    assert mock_s3.put_object.call_count == 2


@pytest.mark.django_db
def test_sign_rejects_bad_hash(api_client, doctor, appointment, settings):
    settings.DOCUMENTS_DATA_S3_BUCKET = "test-bucket"
    api_client.force_authenticate(user=doctor)
    r = api_client.post("/api/consent-documents/", {"appointment": appointment.id}, format="json")
    cid = r.json()["id"]
    r2 = api_client.post(
        f"/api/consent-documents/{cid}/sign/",
        {
            "content_hash": "0" * 64,
            "signature": SimpleUploadedFile("sig.png", _MIN_PNG, content_type="image/png"),
        },
        format="multipart",
    )
    assert r2.status_code == 400


@pytest.mark.django_db
def test_list_filter_appointment(api_client, doctor, appointment, settings):
    settings.DOCUMENTS_DATA_S3_BUCKET = "test-bucket"
    api_client.force_authenticate(user=doctor)
    api_client.post("/api/consent-documents/", {"appointment": appointment.id}, format="json")
    r = api_client.get("/api/consent-documents/", {"appointment": appointment.id})
    assert r.status_code == 200
    data = r.json()
    results = data["results"] if isinstance(data, dict) else data
    assert len(results) >= 1
