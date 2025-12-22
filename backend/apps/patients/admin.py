from django.contrib import admin

from apps.clients.models import ClientClinic

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
        "created_at",
    )
    search_fields = ("name", "species", "breed", "microchip_no", "owner__last_name")
    list_filter = ("clinic", "species")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        # Ensure owner is linked to this clinic
        ClientClinic.objects.get_or_create(
            client=obj.owner,
            clinic=obj.clinic,
            defaults={"is_active": True},
        )
