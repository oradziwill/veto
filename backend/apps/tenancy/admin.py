from django.contrib import admin

from .models import Clinic, ClinicHoliday, ClinicNetwork


@admin.register(ClinicNetwork)
class ClinicNetworkAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "network", "slug", "phone", "email", "created_at")
    list_filter = ("network",)
    search_fields = ("name", "slug")
    autocomplete_fields = ("network",)


@admin.register(ClinicHoliday)
class ClinicHolidayAdmin(admin.ModelAdmin):
    list_display = ("id", "clinic", "date", "reason", "is_active", "created_at")
    list_filter = ("clinic", "is_active")
    search_fields = ("clinic__name", "reason")
    ordering = ("-date",)
