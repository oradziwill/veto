from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_audit_event
from apps.billing.models import Invoice, Payment
from apps.scheduling.models import Appointment

from .authentication import PortalPrincipal
from .permissions import IsPortalClient
from .services.stripe_deposit import (
    create_deposit_checkout_session,
    fulfill_from_checkout_session_payload,
    fulfill_from_retrieved_checkout_session,
    stripe_configured,
    validate_portal_redirect_url,
)
from .view_helpers import portal_appointment_booking_payload, portal_deposit_lookup


class PortalInvoiceCompleteDepositView(APIView):
    """
    POST /api/portal/invoices/<invoice_id>/complete-deposit/

    - ``stripe_session_id``: after Stripe Checkout redirect (or webhook already ran).
    - ``simulated: true``: dev/test payment (when allowed by settings).
    """

    permission_classes = [IsPortalClient]

    def post(self, request, invoice_id: int):
        assert isinstance(request.user, PortalPrincipal)
        p = request.user
        stripe_session_id = (request.data.get("stripe_session_id") or "").strip()
        use_simulated = bool(request.data.get("simulated"))

        appt, inv, err = portal_deposit_lookup(p, invoice_id)
        if err:
            return err

        if stripe_session_id:
            if not stripe_configured():
                return Response(
                    {"detail": "Stripe is not configured on this server."},
                    status=501,
                )
            import stripe

            stripe.api_key = settings.STRIPE_SECRET_KEY
            ref = f"stripe:{stripe_session_id}"
            if inv.status == Invoice.Status.PAID:
                if Payment.objects.filter(invoice_id=inv.id, reference=ref).exists():
                    inv_done = (
                        Invoice.objects.filter(pk=invoice_id)
                        .prefetch_related("lines", "payments")
                        .get()
                    )
                    appt_done = Appointment.objects.get(pk=appt.pk)
                    return Response(
                        portal_appointment_booking_payload(appt_done, inv_done), status=200
                    )
                return Response({"detail": "Invoice is already paid."}, status=400)
            if inv.status != Invoice.Status.DRAFT:
                return Response(
                    {"detail": "Only draft deposit invoices can be completed here."},
                    status=400,
                )
            try:
                session = stripe.checkout.Session.retrieve(stripe_session_id)
            except stripe.StripeError:
                return Response({"detail": "Could not verify payment session."}, status=502)
            meta = getattr(session, "metadata", None) or {}
            if str(meta.get("invoice_id")) != str(invoice_id):
                return Response(
                    {"detail": "Payment session does not match this invoice."}, status=400
                )
            try:
                outcome = fulfill_from_retrieved_checkout_session(session)
            except ValueError as e:
                return Response({"detail": str(e)}, status=400)
            if outcome.should_audit:
                log_audit_event(
                    clinic_id=outcome.appointment.clinic_id,
                    actor=None,
                    action="portal_booking_deposit_paid",
                    entity_type="appointment",
                    entity_id=outcome.appointment.id,
                    after={
                        "invoice_id": outcome.invoice.id,
                        "appointment_status": outcome.appointment.status,
                    },
                    metadata={
                        "source": "portal",
                        "simulated": False,
                        "stripe_session_id": stripe_session_id,
                    },
                )
            return Response(
                portal_appointment_booking_payload(outcome.appointment, outcome.invoice),
                status=200,
            )

        if use_simulated:
            if not (getattr(settings, "PORTAL_ALLOW_SIMULATED_PAYMENT", False) or settings.DEBUG):
                return Response(
                    {"detail": "Simulated payments are disabled on this server."},
                    status=403,
                )
            if inv.status == Invoice.Status.PAID:
                return Response({"detail": "Invoice is already paid."}, status=400)
            if inv.status != Invoice.Status.DRAFT:
                return Response(
                    {"detail": "Only draft deposit invoices can be completed here."},
                    status=400,
                )

            with transaction.atomic():
                inv_locked = Invoice.objects.select_for_update().get(pk=inv.pk)
                appt_locked = Appointment.objects.select_for_update().get(pk=appt.pk)
                Payment.objects.create(
                    invoice=inv_locked,
                    amount=inv_locked.total,
                    method=Payment.Method.CARD,
                    status=Payment.Status.COMPLETED,
                    reference="portal-simulated",
                    note="Portal simulated deposit",
                    created_by=None,
                )
                inv_reload = (
                    Invoice.objects.filter(pk=inv_locked.pk)
                    .prefetch_related("lines", "payments")
                    .get()
                )
                if inv_reload.amount_paid >= inv_reload.total:
                    inv_reload.status = Invoice.Status.PAID
                    inv_reload.save(update_fields=["status", "updated_at"])
                if appt_locked.status != Appointment.Status.CONFIRMED:
                    appt_locked.status = Appointment.Status.CONFIRMED
                    appt_locked.save(update_fields=["status", "updated_at"])

            appt_done = Appointment.objects.get(pk=appt.pk)
            inv_done = (
                Invoice.objects.filter(pk=invoice_id).prefetch_related("lines", "payments").get()
            )
            log_audit_event(
                clinic_id=appt_done.clinic_id,
                actor=None,
                action="portal_booking_deposit_paid",
                entity_type="appointment",
                entity_id=appt_done.id,
                after={
                    "invoice_id": inv_done.id,
                    "appointment_status": appt_done.status,
                },
                metadata={"source": "portal", "simulated": True},
            )

            return Response(
                portal_appointment_booking_payload(appt_done, inv_done),
                status=200,
            )

        if stripe_configured():
            return Response(
                {
                    "detail": (
                        "Provide stripe_session_id after Stripe Checkout, "
                        "call POST …/stripe-checkout/ first, or use simulated: true where allowed."
                    )
                },
                status=400,
            )
        return Response(
            {
                "detail": "Payment provider is not configured; use simulated: true where the server allows it."
            },
            status=501,
        )


class PortalInvoiceStripeCheckoutView(APIView):
    """POST /api/portal/invoices/<invoice_id>/stripe-checkout/ — start Stripe Checkout."""

    permission_classes = [IsPortalClient]

    def post(self, request, invoice_id: int):
        assert isinstance(request.user, PortalPrincipal)
        p = request.user
        if not stripe_configured():
            return Response(
                {"detail": "Stripe is not configured on this server."},
                status=501,
            )
        success_url = (request.data.get("success_url") or "").strip()
        cancel_url = (request.data.get("cancel_url") or "").strip()
        if not success_url or not cancel_url:
            return Response(
                {"detail": "success_url and cancel_url are required."},
                status=400,
            )
        if not validate_portal_redirect_url(success_url) or not validate_portal_redirect_url(
            cancel_url
        ):
            return Response({"detail": "Invalid redirect URL."}, status=400)

        appt, inv, err = portal_deposit_lookup(p, invoice_id)
        if err:
            return err
        if inv.status != Invoice.Status.DRAFT:
            return Response(
                {"detail": "Only draft deposit invoices can be paid."},
                status=400,
            )
        try:
            checkout_url, session_id = create_deposit_checkout_session(
                invoice=inv,
                appointment=appt,
                success_url=success_url,
                cancel_url=cancel_url,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        except Exception:
            return Response({"detail": "Could not start payment session."}, status=502)

        return Response({"checkout_url": checkout_url, "session_id": session_id}, status=200)


@method_decorator(csrf_exempt, name="dispatch")
class PortalStripeWebhookView(APIView):
    """
    POST /api/portal/stripe/webhook/
    Configure URL in Stripe Dashboard; use STRIPE_WEBHOOK_SECRET for signature verification.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
        if not secret:
            return Response({"detail": "Webhook not configured."}, status=503)

        import stripe

        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, secret)
        except ValueError:
            return Response({"detail": "Invalid payload."}, status=400)
        except stripe.SignatureVerificationError:
            return Response({"detail": "Invalid signature."}, status=400)

        ev_type = event.get("type") if isinstance(event, dict) else getattr(event, "type", None)
        if ev_type != "checkout.session.completed":
            return Response({"received": True}, status=200)

        if isinstance(event, dict):
            session = (event.get("data") or {}).get("object") or {}
        else:
            data = getattr(event, "data", None)
            session = getattr(data, "object", None) if data is not None else None
        if not session:
            return Response({"received": True}, status=200)
        try:
            outcome = fulfill_from_checkout_session_payload(session)
        except ValueError:
            return Response({"received": True}, status=200)

        if outcome.should_audit:
            sid = session.get("id", "") if isinstance(session, dict) else getattr(session, "id", "")
            log_audit_event(
                clinic_id=outcome.appointment.clinic_id,
                actor=None,
                action="portal_booking_deposit_paid",
                entity_type="appointment",
                entity_id=outcome.appointment.id,
                after={
                    "invoice_id": outcome.invoice.id,
                    "appointment_status": outcome.appointment.status,
                },
                metadata={
                    "source": "portal",
                    "simulated": False,
                    "stripe_session_id": sid,
                    "via": "stripe_webhook",
                },
            )
        return Response({"received": True}, status=200)
