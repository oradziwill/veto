from django.contrib import admin

from apps.documents.models import IngestionDocument


@admin.register(IngestionDocument)
class IngestionDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "job_id",
        "clinic",
        "patient",
        "original_filename",
        "status",
        "created_at",
    )
    list_filter = ("status", "source", "document_type")
    search_fields = ("original_filename", "job_id__startswith")
    readonly_fields = ("job_id", "sha256", "last_error", "created_at", "updated_at")
    raw_id_fields = ("clinic", "patient", "appointment", "lab_order", "uploaded_by")
