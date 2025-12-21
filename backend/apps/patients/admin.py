from django.contrib import admin
from .models import Patient

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "species",
        "breed",
        "owner",
        "primary_vet",
        "clinic",
    )
    search_fields = ("name", "species", "breed", "microchip_no")
    list_filter = ("clinic", "species")
