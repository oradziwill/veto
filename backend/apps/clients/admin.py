from django.contrib import admin

from .models import Client, ClientClinic


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("id", "first_name", "last_name", "phone", "email", "created_at")
    search_fields = ("first_name", "last_name", "phone", "email")
    ordering = ("last_name", "first_name")


@admin.register(ClientClinic)
class ClientClinicAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "clinic", "is_active", "created_at")
    list_filter = ("clinic", "is_active")
    search_fields = (
        "client__first_name",
        "client__last_name",
        "client__email",
        "clinic__name",
    )
