from django.contrib import admin
from .models import Clinic

@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "phone", "email", "created_at")
    search_fields = ("name", "slug")
