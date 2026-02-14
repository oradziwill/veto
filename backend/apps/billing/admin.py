from django.contrib import admin

from .models import Invoice, InvoiceLine, Payment, Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "clinic", "price")
    list_filter = ("clinic",)
    search_fields = ("name", "code")


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 1


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "patient", "clinic", "status", "due_date", "created_at")
    list_filter = ("clinic", "status")
    search_fields = ("client__first_name", "client__last_name")
    inlines = [InvoiceLineInline, PaymentInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "amount", "method", "status", "paid_at")
    list_filter = ("method", "status")
