from django.contrib import admin

from .models import InventoryItem


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "category", "stock_on_hand", "low_stock_threshold", "clinic")
    list_filter = ("category", "clinic")
    search_fields = ("name", "sku")
    ordering = ("name",)
