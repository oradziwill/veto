from __future__ import annotations

import boto3
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsStaffOrVet
from apps.consents.models import ConsentDocument
from apps.consents.serializers import ConsentDocumentSerializer
from apps.consents.services.pdf import build_payload, compute_content_hash, render_consent_pdf_bytes
from apps.scheduling.models import Appointment
from apps.tenancy.access import (
    accessible_clinic_ids,
)


def _get_s3_client():
    region = getattr(settings, "DOCUMENTS_S3_REGION", "us-east-1")
    return boto3.client("s3", region_name=region)


def _require_bucket():
    bucket = getattr(settings, "DOCUMENTS_DATA_S3_BUCKET", None)
    if not bucket:
        raise ValidationError("Document storage is not configured (DOCUMENTS_DATA_S3_BUCKET).")
    return bucket


class ConsentDocumentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
    serializer_class = ConsentDocumentSerializer

    def get_queryset(self):
        qs = (
            ConsentDocument.objects.filter(clinic_id__in=accessible_clinic_ids(self.request.user))
            .select_related("patient", "appointment", "created_by", "signed_by", "clinic")
            .order_by("-created_at")
        )
        ap = self.request.query_params.get("appointment")
        if ap:
            qs = qs.filter(appointment_id=ap)
        return qs

    def create(self, request, *args, **kwargs):
        appointment_id = request.data.get("appointment")
        if not appointment_id:
            raise ValidationError({"appointment": "This field is required."})
        ap = (
            Appointment.objects.filter(
                id=appointment_id, clinic_id__in=accessible_clinic_ids(request.user)
            )
            .select_related("patient__owner", "vet", "clinic")
            .first()
        )
        if not ap:
            raise ValidationError({"appointment": "Appointment not found."})
        location_label = (request.data.get("location_label") or "")[:120]
        payload = build_payload(ap)
        content_hash = compute_content_hash(payload)
        with transaction.atomic():
            doc = ConsentDocument.objects.create(
                clinic_id=ap.clinic_id,
                appointment=ap,
                patient_id=ap.patient_id,
                document_type=ConsentDocument.DocumentType.PROCEDURE,
                status=ConsentDocument.Status.PENDING_SIGNATURE,
                payload_snapshot=payload,
                content_hash=content_hash,
                created_by=request.user,
                location_label=location_label,
            )
        return Response(
            self.get_serializer(doc).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        doc = self.get_object()
        pdf_bytes = render_consent_pdf_bytes(doc.payload_snapshot, None)
        return HttpResponse(pdf_bytes, content_type="application/pdf")

    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
    )
    def sign(self, request, pk=None):
        doc = self.get_object()
        if doc.status != ConsentDocument.Status.PENDING_SIGNATURE:
            raise ValidationError("Document is not awaiting signature.")
        expected_hash = request.data.get("content_hash") or request.POST.get("content_hash")
        if not expected_hash or expected_hash != doc.content_hash:
            raise ValidationError({"content_hash": "Mismatch or missing; refresh and try again."})
        upload = request.FILES.get("signature") or request.FILES.get("file")
        if not upload:
            raise ValidationError({"signature": "PNG signature file is required."})
        png_bytes = upload.read()
        if len(png_bytes) < 50:
            raise ValidationError({"signature": "Signature image is too small."})
        if not png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValidationError({"signature": "Expected a PNG image."})

        bucket = _require_bucket()
        pdf_bytes = render_consent_pdf_bytes(doc.payload_snapshot, png_bytes)
        job = str(doc.job_id)
        pdf_key = f"consents/{job}/final.pdf"
        png_key = f"consents/{job}/signature.png"

        client = _get_s3_client()
        try:
            client.put_object(
                Bucket=bucket,
                Key=pdf_key,
                Body=pdf_bytes,
                ContentType="application/pdf",
            )
            client.put_object(
                Bucket=bucket,
                Key=png_key,
                Body=png_bytes,
                ContentType="image/png",
            )
        except Exception as e:
            raise ValidationError(f"Storage error: {e}") from e

        with transaction.atomic():
            doc.status = ConsentDocument.Status.SIGNED
            doc.final_pdf_s3_key = pdf_key
            doc.signature_png_s3_key = png_key
            doc.signed_at = timezone.now()
            doc.signed_by = request.user
            doc.save(
                update_fields=[
                    "status",
                    "final_pdf_s3_key",
                    "signature_png_s3_key",
                    "signed_at",
                    "signed_by",
                    "updated_at",
                ]
            )

        return Response(self.get_serializer(doc).data)

    @action(detail=True, methods=["post"], url_path="download-url")
    def download_url(self, request, pk=None):
        doc = self.get_object()
        if doc.status != ConsentDocument.Status.SIGNED:
            raise ValidationError("Document is not signed yet.")
        bucket = _require_bucket()
        key = doc.final_pdf_s3_key
        if not key:
            raise ValidationError("No PDF stored for this document.")
        client = _get_s3_client()
        expires_in = 3600
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return Response({"url": url, "expires_in": expires_in})
