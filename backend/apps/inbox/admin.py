from django.contrib import admin

from apps.inbox.models import InboxTask


@admin.register(InboxTask)
class InboxTaskAdmin(admin.ModelAdmin):
    list_display = ["id", "task_type", "vet", "status", "patient_name", "created_by", "created_at"]
    list_filter = ["status", "task_type"]
    search_fields = ["note", "patient_name", "vet__username"]
