"""
Billing API views.
"""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsStaffOrVet

from .models import Invoice, Payment, Service
from .serializers import (
    InvoiceReadSerializer,
    InvoiceWriteSerializer,
    PaymentSerializer,
    PaymentWriteSerializer,
    ServiceSerializer,
    ServiceWriteSerializer,
)


class ServiceViewSet(viewsets.ModelViewSet):
    """Service catalog - Clinic Admin can manage, all staff can list."""

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        return Service.objects.filter(
            clinic_id=self.request.user.clinic_id
        ).order_by("name")

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return ServiceSerializer
        return ServiceWriteSerializer

    def perform_create(self, serializer):
        serializer.save(clinic_id=self.request.user.clinic_id)


class InvoiceViewSet(viewsets.ModelViewSet):
    """Invoices - Receptionist and Doctor can create/pay, all staff can list."""

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        user = self.request.user
        qs = Invoice.objects.filter(clinic_id=user.clinic_id).select_related(
            "client", "patient", "appointment"
        ).prefetch_related("lines", "payments").order_by("-created_at")

        client_id = self.request.query_params.get("client")
        status = self.request.query_params.get("status")
        if client_id:
            qs = qs.filter(client_id=client_id)
        if status:
            qs = qs.filter(status=status)

        return qs

    def get_serializer_class(self):
        if self.action in ("list", "retrieve", "create", "update", "partial_update"):
            return InvoiceWriteSerializer
        return InvoiceReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()
        return Response(
            InvoiceReadSerializer(invoice).data,
            status=201,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()
        return Response(InvoiceReadSerializer(invoice).data)

    @action(detail=True, methods=["post"], url_path="send")
    def send_invoice(self, request, pk=None):
        """Mark invoice as sent (only draft)."""
        invoice = self.get_object()
        if invoice.status != Invoice.Status.DRAFT:
            return Response(
                {"detail": "Only draft invoices can be sent."},
                status=400,
            )
        invoice.status = Invoice.Status.SENT
        invoice.save(update_fields=["status", "updated_at"])
        return Response(InvoiceReadSerializer(invoice).data)

    @action(detail=True, methods=["get", "post"], url_path="payments")
    def payments_list_or_create(self, request, pk=None):
        """GET: list payments. POST: record a new payment."""
        invoice = self.get_object()
        if request.method == "GET":
            payments = invoice.payments.all().order_by("-paid_at")
            return Response(PaymentSerializer(payments, many=True).data)

        serializer = PaymentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = Payment.objects.create(
            invoice=invoice,
            created_by=request.user,
            **serializer.validated_data,
        )
        if payment.status == "completed":
            total_paid = invoice.amount_paid
            if total_paid >= invoice.total:
                invoice.status = Invoice.Status.PAID
                invoice.save(update_fields=["status", "updated_at"])
        return Response(PaymentSerializer(payment).data, status=201)
