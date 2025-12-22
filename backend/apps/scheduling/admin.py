from django.contrib import admin

from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("id", "clinic", "starts_at", "ends_at", "status", "patient", "vet")
    list_filter = ("clinic", "status", "vet")
    search_fields = ("patient__name", "vet__username", "reason")
    ordering = ("-starts_at",)

    autocomplete_fields = ("patient", "vet")
