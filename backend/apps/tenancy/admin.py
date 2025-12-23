from django.contrib import admin

from .models import Clinic, ClinicHoliday


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "phone", "email", "created_at")
    search_fields = ("name", "slug")


@admin.register(ClinicHoliday)
class ClinicHolidayAdmin(admin.ModelAdmin):
    list_display = ("id", "clinic", "date", "reason", "is_active", "created_at")
    list_filter = ("clinic", "is_active")
    search_fields = ("clinic__name", "reason")
    ordering = ("-date",)
