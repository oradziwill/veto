from django.contrib import admin

from .models import ClinicProductMapping, ReferenceProduct, SyncRun


@admin.register(ReferenceProduct)
class ReferenceProductAdmin(admin.ModelAdmin):
    list_display = ("name", "external_source", "external_id", "last_synced_at", "updated_at")
    list_filter = ("external_source",)
    search_fields = ("name", "common_name", "external_id")


@admin.register(SyncRun)
class SyncRunAdmin(admin.ModelAdmin):
    list_display = ("started_at", "status", "mode", "records_processed", "finished_at")
    list_filter = ("status", "mode")
    readonly_fields = ("started_at", "finished_at", "detail")


@admin.register(ClinicProductMapping)
class ClinicProductMappingAdmin(admin.ModelAdmin):
    list_display = ("clinic", "inventory_item", "reference_product", "is_preferred", "updated_at")
    list_filter = ("clinic", "is_preferred")
    autocomplete_fields = ("clinic", "inventory_item", "reference_product")
    search_fields = ("local_alias", "notes")
