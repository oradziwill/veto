"""Shared helpers for portal HTTP views."""

from __future__ import annotations

import secrets
import string

from django.conf import settings
from rest_framework.response import Response

from apps.billing.models import Invoice
from apps.scheduling.models import Appointment
from apps.scheduling.services.availability import compute_availability
from apps.tenancy.models import Clinic

from .authentication import PortalPrincipal


def generate_portal_code() -> str:
    digits = string.digits
    return "".join(secrets.choice(digits) for _ in range(6))


def get_clinic_by_slug(slug: str) -> Clinic | None:
    return (
        Clinic.objects.filter(slug=slug)
        .only(
            "id",
            "slug",
            "name",
            "online_booking_enabled",
            "portal_booking_deposit_amount",
            "portal_booking_deposit_line_label",
        )
        .first()
    )


def portal_appointment_booking_payload(appt: Appointment, invoice: Invoice | None) -> dict:
    payload = {
        "id": appt.id,
        "starts_at": appt.starts_at.isoformat(),
        "ends_at": appt.ends_at.isoformat(),
        "status": appt.status,
        "reason": appt.reason,
        "vet_id": appt.vet_id,
        "patient_id": appt.patient_id,
        "payment_required": False,
        "deposit_invoice_id": None,
        "deposit_net_pln": None,
        "deposit_gross_pln": None,
    }
    if invoice:
        line = invoice.lines.first()
        payload["payment_required"] = invoice.status != Invoice.Status.PAID
        payload["deposit_invoice_id"] = invoice.id
        payload["deposit_net_pln"] = str(invoice.total)
        payload["deposit_gross_pln"] = str(line.line_gross) if line else str(invoice.total)
    return payload


def portal_deposit_lookup(
    p: PortalPrincipal, invoice_id: int
) -> tuple[Appointment | None, Invoice | None, Response | None]:
    appt = Appointment.objects.filter(
        portal_deposit_invoice_id=invoice_id,
        clinic_id=p.portal_clinic_id,
        patient__owner_id=p.client_id,
    ).first()
    if not appt:
        return None, None, Response({"detail": "Invoice not found."}, status=404)
    inv = Invoice.objects.filter(
        pk=invoice_id,
        clinic_id=p.portal_clinic_id,
        client_id=p.client_id,
    ).first()
    if not inv or appt.portal_deposit_invoice_id != inv.id:
        return None, None, Response({"detail": "Invoice not found."}, status=404)
    if appt.status == Appointment.Status.CANCELLED:
        return (
            None,
            None,
            Response(
                {"detail": "Appointment was cancelled; cannot complete payment."},
                status=409,
            ),
        )
    return appt, inv, None


def public_clinic_or_404(slug: str) -> tuple[Response | None, Clinic | None]:
    clinic = get_clinic_by_slug(slug)
    if not clinic:
        return Response({"detail": "Clinic not found."}, status=404), None
    if not clinic.online_booking_enabled:
        return (
            Response(
                {"detail": "Online booking is disabled for this clinic."},
                status=403,
            ),
            None,
        )
    return None, clinic


def dump_public_availability(
    clinic_id: int, date_str: str, vet_id: int | None, room_id: int | None
):
    slot = int(getattr(settings, "DEFAULT_SLOT_MINUTES", 30))
    data = compute_availability(
        clinic_id=clinic_id,
        date_str=date_str,
        vet_id=vet_id,
        room_id=room_id,
        slot_minutes=slot,
    )

    def dump_interval(interval):
        return {
            "start": interval.start.isoformat(),
            "end": interval.end.isoformat(),
        }

    work_bounds = data.get("work_bounds")
    return {
        "date": date_str,
        "timezone": data["timezone"],
        "clinic_id": clinic_id,
        "default_slot_minutes": data["slot_minutes"],
        "vet_id": vet_id,
        "room_id": room_id,
        "closed_reason": data.get("closed_reason"),
        "workday": dump_interval(work_bounds) if work_bounds else None,
        "free": [dump_interval(i) for i in data["free_slots"]],
    }
