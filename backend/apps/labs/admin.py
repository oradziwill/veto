from django.contrib import admin

from .models import Lab, LabOrder, LabOrderLine, LabResult, LabTest


@admin.register(Lab)
class LabAdmin(admin.ModelAdmin):
    list_display = ("name", "lab_type", "clinic", "is_active")


@admin.register(LabTest)
class LabTestAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "lab", "is_active")


class LabOrderLineInline(admin.TabularInline):
    model = LabOrderLine
    extra = 1


@admin.register(LabOrder)
class LabOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "lab", "status", "ordered_at")
    list_filter = ("status",)
    inlines = [LabOrderLineInline]


@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display = ("order_line", "value", "value_numeric", "status")
