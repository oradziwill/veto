import csv
from datetime import timedelta
from io import StringIO

from django.db.models import Count
from django.utils import timezone

from apps.billing.models import Invoice, InvoiceLine, Payment
from apps.reminders.models import Reminder
from apps.scheduling.models import Appointment

from .models import ReportExportJob


def _as_date(value, default_date):
    if not value:
        return default_date
    return timezone.datetime.fromisoformat(str(value)).date()


def _as_bool(params: dict, key: str, *, default: bool = False) -> bool:
    v = params.get(key)
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in ("1", "true", "yes")


def build_report_csv(job: ReportExportJob) -> tuple[str, str]:
    today = timezone.localdate()
    params = job.params or {}

    if job.report_type == ReportExportJob.ReportType.REVENUE_SUMMARY:
        date_from = _as_date(params.get("from"), today - timedelta(days=30))
        date_to = _as_date(params.get("to"), today)
        lines = (
            InvoiceLine.objects.filter(
                invoice__clinic_id=job.clinic_id,
                invoice__created_at__date__gte=date_from,
                invoice__created_at__date__lte=date_to,
            )
            .exclude(invoice__status=Invoice.Status.CANCELLED)
            .select_related("invoice")
        )
        paid_map = dict(
            Payment.objects.filter(
                invoice__clinic_id=job.clinic_id,
                status=Payment.Status.COMPLETED,
                paid_at__date__gte=date_from,
                paid_at__date__lte=date_to,
            )
            .values("invoice_id")
            .annotate(amount=Count("id"))
            .values_list("invoice_id", "amount")
        )

        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["invoice_id", "created_date", "status", "line_total", "payments_count"])
        for line in lines:
            writer.writerow(
                [
                    line.invoice_id,
                    line.invoice.created_at.date().isoformat(),
                    line.invoice.status,
                    str(line.line_total),
                    paid_map.get(line.invoice_id, 0),
                ]
            )
        return (
            f"revenue-summary-{date_from.isoformat()}-to-{date_to.isoformat()}.csv",
            buffer.getvalue(),
        )

    if job.report_type == ReportExportJob.ReportType.REMINDER_ANALYTICS:
        date_from = _as_date(params.get("from"), today - timedelta(days=30))
        date_to = _as_date(params.get("to"), today)
        rows = (
            Reminder.objects.filter(
                clinic_id=job.clinic_id,
                created_at__date__gte=date_from,
                created_at__date__lte=date_to,
            )
            .values("status", "channel", "provider")
            .annotate(total=Count("id"))
            .order_by("status", "channel", "provider")
        )
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["status", "channel", "provider", "total"])
        for row in rows:
            writer.writerow([row["status"], row["channel"], row["provider"], row["total"]])
        return (
            f"reminder-analytics-{date_from.isoformat()}-to-{date_to.isoformat()}.csv",
            buffer.getvalue(),
        )

    if job.report_type == ReportExportJob.ReportType.CANCELLATION_ANALYTICS:
        date_from = _as_date(params.get("date_from"), today - timedelta(days=30))
        date_to = _as_date(params.get("date_to"), today)
        rows = (
            Appointment.objects.filter(
                clinic_id=job.clinic_id,
                starts_at__date__gte=date_from,
                starts_at__date__lte=date_to,
                status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW],
            )
            .values("status", "cancelled_by")
            .annotate(total=Count("id"))
            .order_by("status", "cancelled_by")
        )
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["status", "cancelled_by", "total"])
        for row in rows:
            writer.writerow([row["status"], row["cancelled_by"], row["total"]])
        return (
            f"cancellation-analytics-{date_from.isoformat()}-to-{date_to.isoformat()}.csv",
            buffer.getvalue(),
        )

    if job.report_type == ReportExportJob.ReportType.ACCOUNTING_INVOICE_LINES:
        date_from = _as_date(params.get("from"), today - timedelta(days=30))
        date_to = _as_date(params.get("to"), today)
        statuses = [
            Invoice.Status.SENT,
            Invoice.Status.PAID,
            Invoice.Status.OVERDUE,
        ]
        if _as_bool(params, "include_drafts"):
            statuses.append(Invoice.Status.DRAFT)
        if _as_bool(params, "include_cancelled"):
            statuses.append(Invoice.Status.CANCELLED)

        lines = (
            InvoiceLine.objects.filter(
                invoice__clinic_id=job.clinic_id,
                invoice__created_at__date__gte=date_from,
                invoice__created_at__date__lte=date_to,
                invoice__status__in=statuses,
            )
            .select_related(
                "invoice",
                "invoice__client",
                "invoice__patient",
                "service",
                "inventory_item",
            )
            .order_by("invoice__created_at", "invoice_id", "id")
        )

        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "invoice_id",
                "invoice_number",
                "invoice_created_date",
                "invoice_status",
                "currency",
                "due_date",
                "client_id",
                "client_name",
                "patient_id",
                "line_id",
                "line_description",
                "quantity",
                "unit",
                "unit_price",
                "vat_rate",
                "line_net",
                "line_vat",
                "line_gross",
                "service_id",
                "inventory_item_id",
            ]
        )
        for line in lines:
            inv = line.invoice
            client = inv.client
            client_name = f"{client.first_name} {client.last_name}".strip()
            writer.writerow(
                [
                    inv.id,
                    inv.invoice_number or "",
                    inv.created_at.date().isoformat(),
                    inv.status,
                    inv.currency,
                    inv.due_date.isoformat() if inv.due_date else "",
                    client.id,
                    client_name,
                    inv.patient_id or "",
                    line.id,
                    line.description,
                    str(line.quantity),
                    line.unit,
                    str(line.unit_price),
                    line.vat_rate,
                    str(line.line_total),
                    str(line.line_vat_amount),
                    str(line.line_gross),
                    line.service_id or "",
                    line.inventory_item_id or "",
                ]
            )
        return (
            f"accounting-invoice-lines-{date_from.isoformat()}-to-{date_to.isoformat()}.csv",
            buffer.getvalue(),
        )

    raise ValueError(f"Unsupported report_type: {job.report_type}")
