from django.contrib import admin

from .models import Appointment, Room
from .models_exceptions import VetAvailabilityException
from .models_working_hours import VetWorkingHours


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("clinic", "name", "display_order")
    list_filter = ("clinic",)
    search_fields = ("name",)
    ordering = ("clinic", "display_order", "name")


@admin.register(VetWorkingHours)
class VetWorkingHoursAdmin(admin.ModelAdmin):
    list_display = ("vet", "weekday", "start_time", "end_time", "is_active")
    list_filter = ("weekday", "is_active")
    search_fields = ("vet__username", "vet__first_name", "vet__last_name")


@admin.register(VetAvailabilityException)
class VetAvailabilityExceptionAdmin(admin.ModelAdmin):
    list_display = ("clinic", "vet", "date", "is_day_off", "start_time", "end_time", "note")
    list_filter = ("clinic", "is_day_off", "date")
    search_fields = ("vet__username", "vet__first_name", "vet__last_name", "note")
    ordering = ("-date",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("clinic", "vet", "patient", "room", "starts_at", "ends_at", "status")
    list_filter = ("clinic", "status", "vet")
    search_fields = ("patient__name", "vet__username")
