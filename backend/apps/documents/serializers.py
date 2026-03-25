from __future__ import annotations

from rest_framework import serializers

from apps.documents.models import IngestionDocument


class IngestionDocumentSerializer(serializers.ModelSerializer):
    """Read serializer for list/retrieve."""

    class Meta:
        model = IngestionDocument
        fields = [
            "id",
            "job_id",
            "clinic",
            "patient",
            "appointment",
            "lab_order",
            "document_type",
            "source",
            "original_filename",
            "content_type",
            "size_bytes",
            "sha256",
            "status",
            "last_error",
            "input_s3_key",
            "output_html_s3_key",
            "uploaded_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class IngestionDocumentUploadResponseSerializer(serializers.ModelSerializer):
    """Minimal response after upload (201)."""

    class Meta:
        model = IngestionDocument
        fields = ["id", "job_id", "status", "input_s3_key", "created_at"]
