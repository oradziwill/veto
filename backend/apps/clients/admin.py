from django.contrib import admin
from .models import Client

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("id", "first_name", "last_name", "phone", "email", "clinic")
    search_fields = ("first_name", "last_name", "phone", "email")
    list_filter = ("clinic",)
