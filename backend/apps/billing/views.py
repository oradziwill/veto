"""
Billing API views.
"""

import calendar
import csv
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.db.models import Count, DecimalField, F, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsAdminOrReadOnly, IsClinicAdmin, IsStaffOrVet
from apps.tenancy.access import accessible_clinic_ids, clinic_id_for_mutation

from .ksef_service import KSeFError
from .ksef_service import submit_invoice as ksef_submit
from .ksef_xml import build_fa3_xml
from .models import Invoice, InvoiceLine, Payment, Service
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

    permission_classes = [IsAuthenticated, HasClinic, IsAdminOrReadOnly]

    def get_queryset(self):
        return Service.objects.filter(
            clinic_id__in=accessible_clinic_ids(self.request.user)
        ).order_by("name")

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return ServiceSerializer
        return ServiceWriteSerializer

    def perform_create(self, serializer):
        cid = clinic_id_for_mutation(
            self.request.user, request=self.request, instance_clinic_id=None
        )
        serializer.save(clinic_id=cid)


class InvoiceViewSet(viewsets.ModelViewSet):
    """Invoices - Receptionist and Doctor can create/pay, all staff can list."""

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        user = self.request.user
        qs = (
            Invoice.objects.filter(clinic_id__in=accessible_clinic_ids(user))
            .select_related("client", "patient", "appointment")
            .prefetch_related("lines", "payments")
            .order_by("-created_at")
        )

        client_id = self.request.query_params.get("client")
        status = self.request.query_params.get("status")
        if client_id:
            qs = qs.filter(client_id=client_id)
        if status:
            qs = qs.filter(status=status)

        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
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

    @action(detail=True, methods=["post"], url_path="submit-ksef")
    def submit_ksef(self, request, pk=None):
        """Build FA3 XML and submit this invoice to KSeF."""
        invoice = self.get_object()
        if invoice.ksef_status == "accepted":
            return Response({"detail": "Invoice already accepted by KSeF."}, status=400)

        try:
            xml_bytes = build_fa3_xml(invoice)
            invoice.ksef_status = "pending"
            invoice.save(update_fields=["ksef_status", "updated_at"])

            reference = ksef_submit(invoice, xml_bytes)

            invoice.ksef_number = reference
            invoice.ksef_status = "accepted"
            invoice.save(update_fields=["ksef_number", "ksef_status", "updated_at"])

            return Response(InvoiceReadSerializer(invoice).data)
        except KSeFError as exc:
            invoice.ksef_status = "error"
            invoice.save(update_fields=["ksef_status", "updated_at"])
            return Response({"detail": str(exc)}, status=502)

    @action(detail=True, methods=["get"], url_path="ksef-xml")
    def ksef_xml_preview(self, request, pk=None):
        """Return the FA3 XML for this invoice (for preview/debugging)."""
        invoice = self.get_object()
        xml_bytes = build_fa3_xml(invoice)
        from django.http import HttpResponse

        return HttpResponse(xml_bytes, content_type="application/xml; charset=utf-8")

    @action(detail=True, methods=["get", "post"], url_path="payments")
    def payments_list_or_create(self, request, pk=None):
        """GET: list payments. POST: record a new payment."""
        invoice = self.get_object()
        if request.method == "GET":
            payments = invoice.payments.all().order_by("-paid_at")
            return Response(PaymentSerializer(payments, many=True).data)

        serializer = PaymentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        Payment.objects.create(
            invoice=invoice,
            created_by=request.user,
            **serializer.validated_data,
        )
        invoice = (
            Invoice.objects.filter(pk=invoice.pk)
            .select_related("client", "patient", "appointment")
            .prefetch_related("lines", "payments")
            .get()
        )
        if invoice.amount_paid >= invoice.total:
            invoice.status = Invoice.Status.PAID
            invoice.save(update_fields=["status", "updated_at"])
        return Response(InvoiceReadSerializer(invoice).data, status=201)


def _parse_date(value):
    """Parse YYYY-MM-DD to date or None."""
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _periods_in_range(date_from, date_to, period_kind):
    """Yield (period_date, label) for each period in [date_from, date_to]."""
    if period_kind == "monthly":
        current = date(date_from.year, date_from.month, 1)
        end = date(date_to.year, date_to.month, 1)
        while current <= end:
            yield current, current.strftime("%Y-%m")
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)
    else:
        current = date_from
        while current <= date_to:
            yield current, current.strftime("%Y-%m-%d")
            current = current + timedelta(days=1)


def _last_n_months_range(today, n):
    """Return (date_from, date_to) for the last n calendar months ending with current month."""
    if n < 1:
        return today, today
    end_year, end_month = today.year, today.month
    start_month = end_month - (n - 1)
    start_year = end_year
    while start_month < 1:
        start_month += 12
        start_year -= 1
    date_from = date(start_year, start_month, 1)
    _, last_day = calendar.monthrange(end_year, end_month)
    date_to = date(end_year, end_month, last_day)
    if date_to > today:
        date_to = today
    return date_from, date_to


class RevenueSummaryView(APIView):
    """GET /api/billing/revenue-summary/ – Admin-only revenue summary by period."""

    permission_classes = [IsAuthenticated, HasClinic, IsClinicAdmin]

    @staticmethod
    def _wants_csv(request) -> bool:
        return (request.query_params.get("export") or "").strip().lower() == "csv"

    @staticmethod
    def _csv_response(*, filename: str, headers: list[str], rows: list[list[str]]):
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        writer.writerows(rows)
        response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def get(self, request):
        period_param = (request.query_params.get("period") or "monthly").strip().lower()
        if period_param not in ("monthly", "daily"):
            return Response(
                {"detail": "Invalid period. Use 'monthly' or 'daily'."},
                status=400,
            )
        period_kind = period_param

        breakdown_param = (request.query_params.get("breakdown") or "").strip().lower()
        months_param = request.query_params.get("months")
        if months_param is not None and months_param != "" and breakdown_param != "monthly":
            return Response(
                {"detail": "Parameter 'months' is only valid when breakdown=monthly."},
                status=400,
            )
        if breakdown_param and breakdown_param != "monthly":
            return Response(
                {"detail": "Invalid breakdown. Use 'monthly' or omit."},
                status=400,
            )
        if breakdown_param == "monthly" and months_param is not None:
            try:
                n_months = int(months_param)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "Parameter 'months' must be a positive integer."},
                    status=400,
                )
            if n_months < 1:
                return Response(
                    {"detail": "Parameter 'months' must be a positive integer."},
                    status=400,
                )

        today = timezone.now().date()
        start_of_year = date(today.year, 1, 1)
        date_from = _parse_date(request.query_params.get("from"))
        date_to = _parse_date(request.query_params.get("to"))
        if breakdown_param == "monthly" and date_from is None and date_to is None:
            n = 6
            if months_param not in (None, ""):
                n = int(months_param)
            date_from, date_to = _last_n_months_range(today, n)
        if date_from is None:
            date_from = start_of_year
        if date_to is None:
            date_to = today
        if date_from > date_to:
            return Response(
                {"detail": "'from' must be less than or equal to 'to'."},
                status=400,
            )

        clinic_id = request.user.clinic_id
        if not clinic_id:
            return Response(
                {"detail": "User must belong to a clinic."},
                status=403,
            )

        # Total invoiced: sum of line totals for non-cancelled invoices in range
        line_total_expr = F("quantity") * F("unit_price")
        invoiced_qs = (
            InvoiceLine.objects.filter(
                invoice__clinic_id=clinic_id,
                invoice__created_at__date__gte=date_from,
                invoice__created_at__date__lte=date_to,
            )
            .exclude(invoice__status=Invoice.Status.CANCELLED)
            .aggregate(
                s=Sum(line_total_expr, output_field=DecimalField(max_digits=14, decimal_places=2))
            )
        )
        total_invoiced = invoiced_qs["s"] or Decimal("0")

        # Total paid: sum of completed payments in range
        paid_qs = Payment.objects.filter(
            invoice__clinic_id=clinic_id,
            status=Payment.Status.COMPLETED,
            paid_at__date__gte=date_from,
            paid_at__date__lte=date_to,
        ).aggregate(s=Sum("amount"))
        total_paid = paid_qs["s"] or Decimal("0")
        total_outstanding = total_invoiced - total_paid

        # By period: invoiced and paid grouped by TruncMonth or TruncDate
        if period_kind == "monthly":
            trunc_inv = TruncMonth("invoice__created_at")
            trunc_pay = TruncMonth("paid_at")
        else:
            trunc_inv = TruncDate("invoice__created_at")
            trunc_pay = TruncDate("paid_at")

        invoiced_by_period = (
            InvoiceLine.objects.filter(
                invoice__clinic_id=clinic_id,
                invoice__created_at__date__gte=date_from,
                invoice__created_at__date__lte=date_to,
            )
            .exclude(invoice__status=Invoice.Status.CANCELLED)
            .annotate(period=trunc_inv)
            .values("period")
            .annotate(
                invoiced=Sum(
                    line_total_expr, output_field=DecimalField(max_digits=14, decimal_places=2)
                )
            )
            .order_by("period")
        )
        paid_by_period = (
            Payment.objects.filter(
                invoice__clinic_id=clinic_id,
                status=Payment.Status.COMPLETED,
                paid_at__date__gte=date_from,
                paid_at__date__lte=date_to,
            )
            .annotate(period=trunc_pay)
            .values("period")
            .annotate(paid=Sum("amount"))
            .order_by("period")
        )

        # Build label -> amount maps (period from DB can be date or datetime)
        def to_label(period_value):
            if hasattr(period_value, "date"):
                d = period_value.date()
            else:
                d = period_value
            return d.strftime("%Y-%m") if period_kind == "monthly" else d.strftime("%Y-%m-%d")

        invoiced_map = {
            to_label(row["period"]): row["invoiced"] or Decimal("0") for row in invoiced_by_period
        }
        paid_map = {to_label(row["period"]): row["paid"] or Decimal("0") for row in paid_by_period}

        by_period = []
        for _period_date, label in _periods_in_range(date_from, date_to, period_kind):
            inv = invoiced_map.get(label, Decimal("0"))
            pa = paid_map.get(label, Decimal("0"))
            by_period.append(
                {
                    "label": label,
                    "invoiced": str(inv.quantize(Decimal("0.01"))),
                    "paid": str(pa.quantize(Decimal("0.01"))),
                }
            )

        payload = {
            "period": period_kind,
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
            "total_invoiced": str(total_invoiced.quantize(Decimal("0.01"))),
            "total_paid": str(total_paid.quantize(Decimal("0.01"))),
            "total_outstanding": str(total_outstanding.quantize(Decimal("0.01"))),
            "by_period": by_period,
        }

        if breakdown_param == "monthly":
            invoice_counts = (
                Invoice.objects.filter(
                    clinic_id=clinic_id,
                    created_at__date__gte=date_from,
                    created_at__date__lte=date_to,
                )
                .exclude(status=Invoice.Status.CANCELLED)
                .annotate(period=TruncMonth("created_at"))
                .values("period")
                .annotate(invoice_count=Count("id"))
                .order_by("period")
            )
            count_by_label = {}
            for row in invoice_counts:
                pv = row["period"]
                d = pv.date() if hasattr(pv, "date") else pv
                count_by_label[d.strftime("%Y-%m")] = row["invoice_count"]
            monthly = []
            for _period_date, label in _periods_in_range(date_from, date_to, "monthly"):
                rev = invoiced_map.get(label, Decimal("0"))
                monthly.append(
                    {
                        "month": label,
                        "revenue": str(rev.quantize(Decimal("0.01"))),
                        "invoice_count": count_by_label.get(label, 0),
                    }
                )
            payload["monthly"] = monthly

        if self._wants_csv(request):
            rows = [
                [
                    item["label"],
                    item["invoiced"],
                    item["paid"],
                ]
                for item in payload["by_period"]
            ]
            return self._csv_response(
                filename=f"revenue-summary-{payload['from']}-to-{payload['to']}.csv",
                headers=["label", "invoiced", "paid"],
                rows=rows,
            )

        return Response(payload)
