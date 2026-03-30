"""
Stripe Checkout for portal booking deposits (PLN).
"""

from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple
from urllib.parse import urlparse

from django.conf import settings

from apps.billing.models import Invoice, Payment
from apps.scheduling.models import Appointment


class DepositFulfillOutcome(NamedTuple):
    appointment: Appointment
    invoice: Invoice
    should_audit: bool


def stripe_configured() -> bool:
    return bool(getattr(settings, "STRIPE_SECRET_KEY", ""))


def validate_portal_redirect_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    if not settings.DEBUG and parsed.scheme != "https":
        return False
    return True


def _pln_to_minor_units(amount: Decimal) -> int:
    q = amount.quantize(Decimal("0.01"))
    return int(q * 100)


def invoice_pln_gross_minor(invoice: Invoice) -> int:
    inv = Invoice.objects.filter(pk=invoice.pk).prefetch_related("lines", "payments").get()
    return _pln_to_minor_units(inv.total_gross)


def create_deposit_checkout_session(
    *,
    invoice: Invoice,
    appointment: Appointment,
    success_url: str,
    cancel_url: str,
) -> tuple[str, str]:
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    inv = Invoice.objects.filter(pk=invoice.pk).prefetch_related("lines").get()
    if (inv.currency or "PLN").upper() != "PLN":
        raise ValueError("Stripe portal deposit supports PLN invoices only.")
    line = inv.lines.first()
    label = (line.description if line else "") or "Booking deposit"
    gross = inv.total_gross
    unit_minor = _pln_to_minor_units(gross)
    session = stripe.checkout.Session.create(
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=str(inv.id),
        metadata={
            "invoice_id": str(inv.id),
            "appointment_id": str(appointment.id),
            "clinic_id": str(inv.clinic_id),
        },
        line_items=[
            {
                "price_data": {
                    "currency": "pln",
                    "product_data": {"name": label[:255]},
                    "unit_amount": unit_minor,
                },
                "quantity": 1,
            }
        ],
    )
    url = session.url or ""
    sid = session.id or ""
    if not url or not sid:
        raise RuntimeError("Stripe checkout session missing url or id.")
    return url, sid


def fulfill_deposit_checkout_session(
    *,
    session_id: str,
    payment_status: str,
    amount_total: int | None,
    metadata: dict | str | None,
) -> DepositFulfillOutcome:
    """
    Idempotent: records Payment and confirms appointment when Stripe marks session paid.
    should_audit is False when this session was already recorded (webhook retries).
    """
    from django.db import transaction

    if payment_status != "paid":
        raise ValueError("Checkout session is not paid.")

    if not metadata:
        raise ValueError("Missing session metadata.")

    meta = dict(metadata) if hasattr(metadata, "items") else {}
    invoice_id_raw = meta.get("invoice_id")
    appointment_id_raw = meta.get("appointment_id")
    clinic_id_raw = meta.get("clinic_id")
    if not invoice_id_raw or not appointment_id_raw or not clinic_id_raw:
        raise ValueError("Invalid checkout metadata.")

    try:
        invoice_id = int(invoice_id_raw)
        appointment_id = int(appointment_id_raw)
        clinic_id = int(clinic_id_raw)
    except (TypeError, ValueError) as e:
        raise ValueError("Invalid checkout metadata ids.") from e

    ref = f"stripe:{session_id}"

    with transaction.atomic():
        if Payment.objects.filter(reference=ref).exists():
            appt = Appointment.objects.get(pk=appointment_id)
            inv = Invoice.objects.filter(pk=invoice_id).prefetch_related("lines", "payments").get()
            return DepositFulfillOutcome(appt, inv, False)

        appt = (
            Appointment.objects.select_for_update()
            .filter(
                pk=appointment_id,
                clinic_id=clinic_id,
                portal_deposit_invoice_id=invoice_id,
            )
            .first()
        )
        if not appt:
            raise ValueError("Appointment not found for checkout session.")
        if appt.status == Appointment.Status.CANCELLED:
            raise ValueError("Appointment was cancelled; cannot complete payment.")

        inv = (
            Invoice.objects.select_for_update()
            .filter(pk=invoice_id, clinic_id=clinic_id, client_id=appt.patient.owner_id)
            .prefetch_related("lines", "payments")
            .first()
        )
        if not inv:
            raise ValueError("Invoice not found for checkout session.")
        if inv.status == Invoice.Status.PAID:
            return DepositFulfillOutcome(appt, inv, False)
        if inv.status != Invoice.Status.DRAFT:
            raise ValueError("Only draft deposit invoices can be completed here.")

        expected_minor = invoice_pln_gross_minor(inv)
        if amount_total is None:
            raise ValueError("Missing amount_total from Stripe session.")
        if abs(int(amount_total) - expected_minor) > 1:
            raise ValueError("Paid amount does not match invoice gross total.")

        pay_amount = (Decimal(int(amount_total)) / Decimal(100)).quantize(Decimal("0.01"))
        Payment.objects.create(
            invoice=inv,
            amount=pay_amount,
            method=Payment.Method.CARD,
            status=Payment.Status.COMPLETED,
            reference=ref,
            note="Portal Stripe deposit",
            created_by=None,
        )
        inv_reload = Invoice.objects.filter(pk=inv.pk).prefetch_related("lines", "payments").get()
        if inv_reload.amount_paid >= inv_reload.total:
            inv_reload.status = Invoice.Status.PAID
            inv_reload.save(update_fields=["status", "updated_at"])
        appt_reload = Appointment.objects.select_for_update().get(pk=appt.pk)
        if appt_reload.status != Appointment.Status.CONFIRMED:
            appt_reload.status = Appointment.Status.CONFIRMED
            appt_reload.save(update_fields=["status", "updated_at"])

    appt_done = Appointment.objects.get(pk=appointment_id)
    inv_done = Invoice.objects.filter(pk=invoice_id).prefetch_related("lines", "payments").get()
    return DepositFulfillOutcome(appt_done, inv_done, True)


def fulfill_from_retrieved_checkout_session(session) -> DepositFulfillOutcome:
    """Accepts stripe.checkout.Session instance from retrieve."""
    return fulfill_deposit_checkout_session(
        session_id=session.id,
        payment_status=session.payment_status,
        amount_total=session.amount_total,
        metadata=session.metadata,
    )


def fulfill_from_checkout_session_payload(session) -> DepositFulfillOutcome:
    """Dict from webhook JSON or StripeObject from retrieve."""
    if isinstance(session, dict):
        return fulfill_deposit_checkout_session(
            session_id=session["id"],
            payment_status=session.get("payment_status") or "",
            amount_total=session.get("amount_total"),
            metadata=session.get("metadata"),
        )
    return fulfill_from_retrieved_checkout_session(session)
