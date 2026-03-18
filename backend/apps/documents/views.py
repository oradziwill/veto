from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path

import boto3
from django.conf import settings
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsStaffOrVet
from apps.documents.models import IngestionDocument
from apps.documents.serializers import (
    IngestionDocumentSerializer,
    IngestionDocumentUploadResponseSerializer,
)
from apps.patients.models import Patient

# Allowed content types for MVP: PDF and common images
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}


def _safe_s3_filename(original: str) -> str:
    """Keep extension, sanitize name to avoid path traversal and special chars."""
    stem = Path(original).stem
    suffix = Path(original).suffix
    safe_stem = re.sub(r"[^\w\-.]", "_", stem)[:200]
    safe_suffix = re.sub(r"[^\w.]", "", suffix)[:20]
    return (safe_stem or "file") + (safe_suffix or "")


def _get_s3_client():
    region = getattr(settings, "DOCUMENTS_S3_REGION", "us-east-1")
    return boto3.client("s3", region_name=region)


class DocumentUploadView(APIView):
    """
    POST (multipart): upload file to S3 under documents_data/{job_id}/ and create IngestionDocument.
    Body: file (required), patient (required), optional: appointment, lab_order, document_type.
    """

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def post(self, request):
        bucket = getattr(settings, "DOCUMENTS_DATA_S3_BUCKET", None)
        skip_s3 = not bucket and getattr(settings, "DEBUG", False)
        if not bucket and not skip_s3:
            raise ValidationError("Document storage is not configured (DOCUMENTS_DATA_S3_BUCKET).")

        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            raise ValidationError("Missing 'file' in multipart body.")

        content_type = uploaded_file.content_type or ""
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValidationError(
                {"file": f"Allowed types: PDF, JPEG, PNG, GIF, WebP. Got: {content_type}"}
            )

        max_bytes = getattr(settings, "DOCUMENTS_MAX_UPLOAD_MB", 50) * 1024 * 1024
        if uploaded_file.size > max_bytes:
            raise ValidationError(
                {"file": f"File size exceeds maximum ({settings.DOCUMENTS_MAX_UPLOAD_MB} MB)."}
            )

        patient_id = request.data.get("patient")
        if not patient_id:
            raise ValidationError({"patient": "This field is required."})

        clinic_id = request.user.clinic_id
        patient = Patient.objects.filter(clinic_id=clinic_id, pk=patient_id).first()
        if not patient:
            raise ValidationError({"patient": "Patient not found or not in your clinic."})

        appointment_id = request.data.get("appointment")
        lab_order_id = request.data.get("lab_order")
        document_type = request.data.get("document_type") or IngestionDocument.DocumentType.OTHER

        job_id = uuid.uuid4()
        original_filename = uploaded_file.name or "unnamed"
        safe_filename = _safe_s3_filename(original_filename)
        input_s3_key = f"documents_data/{job_id}/{safe_filename}"

        sha256_hash = hashlib.sha256()
        for chunk in uploaded_file.chunks():
            sha256_hash.update(chunk)
        sha256 = sha256_hash.hexdigest()
        uploaded_file.seek(0)

        if not skip_s3:
            client = _get_s3_client()
            try:
                client.upload_fileobj(
                    uploaded_file,
                    bucket,
                    input_s3_key,
                    ExtraArgs={"ContentType": content_type},
                )
            except Exception as e:
                raise ValidationError({"file": f"Upload to storage failed: {e}"}) from e

        with transaction.atomic():
            doc = IngestionDocument.objects.create(
                clinic_id=clinic_id,
                patient=patient,
                appointment_id=appointment_id or None,
                lab_order_id=lab_order_id or None,
                document_type=document_type,
                source=IngestionDocument.Source.MANUAL_UPLOAD,
                job_id=job_id,
                original_filename=original_filename,
                content_type=content_type,
                size_bytes=uploaded_file.size,
                sha256=sha256,
                status=IngestionDocument.Status.UPLOADED,
                input_s3_key=input_s3_key,
                uploaded_by=request.user,
            )

        serializer = IngestionDocumentUploadResponseSerializer(doc)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class IngestionDocumentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List and retrieve ingestion documents (clinic-scoped).
    Filters: patient, status.
    """

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
    serializer_class = IngestionDocumentSerializer

    def get_queryset(self):
        qs = (
            IngestionDocument.objects.filter(clinic_id=self.request.user.clinic_id)
            .select_related("patient", "clinic", "uploaded_by", "appointment", "lab_order")
            .order_by("-created_at")
        )
        patient_id = self.request.query_params.get("patient")
        status_filter = self.request.query_params.get("status")
        if patient_id:
            qs = qs.filter(patient_id=patient_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    @action(detail=True, methods=["post"], url_path="download-url")
    def download_url(self, request, pk=None):
        """
        Return a presigned URL for the document. Prefer HTML output if ready; otherwise input file.
        """
        doc = self.get_object()
        bucket = getattr(settings, "DOCUMENTS_DATA_S3_BUCKET", None)
        if not bucket:
            raise ValidationError("Document storage is not configured.")

        key = doc.output_html_s3_key or doc.input_s3_key
        if not key:
            raise NotFound("No file available for this document.")

        client = _get_s3_client()
        expires_in = 3600
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return Response({"url": url, "expires_in": expires_in})
