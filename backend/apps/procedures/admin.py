from django.contrib import admin

from .models import ClinicalProcedure, VisitProcedureSession


@admin.register(ClinicalProcedure)
class ClinicalProcedureAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "species", "is_active", "last_reviewed"]
    list_filter = ["category", "is_active"]
    search_fields = ["name", "slug", "tags"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(VisitProcedureSession)
class VisitProcedureSessionAdmin(admin.ModelAdmin):
    list_display = ["procedure", "patient", "doctor", "created_at", "completed_at"]
    list_filter = ["procedure"]
    raw_id_fields = ["appointment", "procedure", "doctor", "patient"]
