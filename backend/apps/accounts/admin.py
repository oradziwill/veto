from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Clinic / network", {"fields": ("clinic", "network", "role", "is_vet")}),
    )
    list_display = UserAdmin.list_display + ("clinic", "network", "role", "is_vet")
    list_filter = UserAdmin.list_filter + ("clinic", "network", "role", "is_vet")
