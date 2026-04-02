from django.contrib import admin

from apps.consents.models import ConsentDocument


@admin.register(ConsentDocument)
class ConsentDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "appointment", "status", "document_type", "created_at", "signed_at")
    list_filter = ("status", "document_type")
    raw_id_fields = ("clinic", "appointment", "patient", "created_by", "signed_by")
