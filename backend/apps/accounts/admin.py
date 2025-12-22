from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Clinic", {"fields": ("clinic", "is_vet")}),)
    list_display = UserAdmin.list_display + ("clinic", "is_vet")
    list_filter = UserAdmin.list_filter + ("clinic", "is_vet")
