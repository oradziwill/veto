from django.contrib import admin

from .models import WebhookDelivery, WebhookSubscription


@admin.register(WebhookSubscription)
class WebhookSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "clinic", "target_url", "is_active", "created_at")
    list_filter = ("is_active", "clinic")
    search_fields = ("target_url", "description")


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ("id", "subscription", "event_type", "status", "http_status", "created_at")
    list_filter = ("status", "event_type")
