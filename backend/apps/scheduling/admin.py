from django.contrib import admin

from .models import Appointment
from .models_working_hours import VetWorkingHours


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("id", "clinic", "patient", "vet", "starts_at", "ends_at", "status")
    list_filter = ("clinic", "status", "vet")
    search_fields = ("patient__name", "vet__username", "vet__first_name", "vet__last_name")


@admin.register(VetWorkingHours)
class VetWorkingHoursAdmin(admin.ModelAdmin):
    list_display = ("id", "vet", "weekday", "start_time", "end_time", "is_active")
    list_filter = ("weekday", "is_active", "vet")
