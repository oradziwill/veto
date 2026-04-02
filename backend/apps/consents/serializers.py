from __future__ import annotations

from rest_framework import serializers

from apps.consents.models import ConsentDocument


class ConsentDocumentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    signed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ConsentDocument
        fields = [
            "id",
            "clinic",
            "appointment",
            "patient",
            "document_type",
            "status",
            "template_version",
            "content_hash",
            "job_id",
            "final_pdf_s3_key",
            "signature_png_s3_key",
            "created_by",
            "created_by_name",
            "signed_at",
            "signed_by",
            "signed_by_name",
            "location_label",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_created_by_name(self, obj):
        u = obj.created_by
        if not u:
            return None
        return f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username

    def get_signed_by_name(self, obj):
        u = obj.signed_by
        if not u:
            return None
        return f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username
