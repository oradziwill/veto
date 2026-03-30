from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timedelta
from datetime import time as dt_time
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.audit.services import log_audit_event
from apps.billing.models import Invoice, InvoiceLine, Payment
from apps.clients.models import ClientClinic
from apps.medical.models import ClinicalExam, Vaccination
from apps.patients.models import Patient
from apps.scheduling.models import Appointment, Room
from apps.scheduling.services.availability import compute_availability
from apps.tenancy.models import Clinic

from .authentication import PortalPrincipal
from .models import PortalLoginChallenge
from .permissions import IsPortalClient
from .services.booking import portal_slot_matches_availability
from .services.confirm_lockout import (
    clear_portal_confirm_failures,
    is_portal_confirm_blocked,
    record_portal_confirm_failure,
)
from .services.magic_link_tokens import digest_magic_token, generate_magic_link_plaintext
from .services.otp_email import send_portal_otp_email, sendgrid_configured
from .services.rate_limit import (
    client_ip_from_request,
    portal_confirm_ip_key,
    portal_confirm_mailbox_key,
    portal_magic_link_ip_key,
    portal_request_code_ip_key,
    portal_request_code_mailbox_key,
    rate_limit_exceeded,
)
from .services.staff_notify_booking import notify_staff_new_portal_booking
from .services.stripe_deposit import (
    create_deposit_checkout_session,
    fulfill_from_checkout_session_payload,
    fulfill_from_retrieved_checkout_session,
    stripe_configured,
    validate_portal_redirect_url,
)
from .tokens import create_portal_access_token

logger = logging.getLogger(__name__)


def _generate_portal_code() -> str:
    digits = string.digits
    return "".join(secrets.choice(digits) for _ in range(6))


def _get_clinic_by_slug(slug: str) -> Clinic | None:
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


def _portal_appointment_booking_payload(appt: Appointment, invoice: Invoice | None) -> dict:
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


def _portal_deposit_lookup(
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


def _public_clinic_or_404(slug: str) -> tuple[Response | None, Clinic | None]:
    clinic = _get_clinic_by_slug(slug)
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


def _dump_public_availability(
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


class PortalClinicPublicView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug: str):
        err, clinic = _public_clinic_or_404(slug)
        if err:
            return err
        return Response(
            {
                "slug": clinic.slug,
                "name": clinic.name,
                "online_booking_enabled": clinic.online_booking_enabled,
                "portal_booking_deposit_pln": str(clinic.portal_booking_deposit_amount),
                "portal_booking_deposit_label": clinic.portal_booking_deposit_line_label,
            }
        )


class PortalClinicVetsPublicView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug: str):
        err, clinic = _public_clinic_or_404(slug)
        if err:
            return err
        vets = (
            User.objects.filter(clinic_id=clinic.id)
            .filter(Q(role=User.Role.DOCTOR) | Q(is_vet=True))
            .order_by("last_name", "first_name", "username")
        )
        payload = [
            {
                "id": v.id,
                "first_name": v.first_name or "",
                "last_name": v.last_name or "",
                "username": v.username,
            }
            for v in vets
        ]
        return Response(payload)


class PortalClinicAvailabilityPublicView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug: str):
        err, clinic = _public_clinic_or_404(slug)
        if err:
            return err
        date_str = request.query_params.get("date")
        if not date_str:
            return Response({"detail": "Missing query param: date=YYYY-MM-DD"}, status=400)
        vet_raw = request.query_params.get("vet")
        vet_id = int(vet_raw) if vet_raw else None
        if vet_id is not None:
            if (
                not User.objects.filter(
                    id=vet_id,
                    clinic_id=clinic.id,
                )
                .filter(Q(role=User.Role.DOCTOR) | Q(is_vet=True))
                .exists()
            ):
                return Response({"detail": "Vet not found in this clinic."}, status=404)
        room_raw = request.query_params.get("room")
        room_id = int(room_raw) if room_raw else None
        body = _dump_public_availability(clinic.id, date_str, vet_id, room_id)
        return Response(body)


class PortalAuthRequestCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        slug = (request.data.get("clinic_slug") or "").strip()
        email = (request.data.get("email") or "").strip().lower()
        if not slug or not email:
            return Response(
                {"detail": "clinic_slug and email are required."},
                status=400,
            )
        ip = client_ip_from_request(request)
        if rate_limit_exceeded(
            portal_request_code_ip_key(ip),
            int(getattr(settings, "PORTAL_OTP_REQUEST_LIMIT_PER_IP", 60)),
            int(getattr(settings, "PORTAL_OTP_REQUEST_IP_WINDOW_SEC", 3600)),
        ):
            return Response(
                {"detail": "Too many requests. Please try again later."},
                status=429,
            )
        if rate_limit_exceeded(
            portal_request_code_mailbox_key(slug, email),
            int(getattr(settings, "PORTAL_OTP_REQUEST_LIMIT_PER_MAILBOX", 10)),
            int(getattr(settings, "PORTAL_OTP_REQUEST_MAILBOX_WINDOW_SEC", 900)),
        ):
            return Response(
                {"detail": "Too many requests. Please try again later."},
                status=429,
            )

        err, clinic = _public_clinic_or_404(slug)
        if err:
            return err

        membership = (
            ClientClinic.objects.filter(
                clinic=clinic,
                is_active=True,
                client__email__iexact=email,
            )
            .select_related("client")
            .first()
        )

        generic = {"detail": "If this email is registered at the clinic, a login code was sent."}
        if not membership:
            return Response(generic, status=200)

        code = _generate_portal_code()
        magic_plain = generate_magic_link_plaintext()
        magic_digest = digest_magic_token(magic_plain)
        link_template = str(getattr(settings, "PORTAL_MAGIC_LINK_URL_TEMPLATE", "") or "").strip()
        magic_url = (
            link_template.replace("{token}", magic_plain) if "{token}" in link_template else None
        )

        PortalLoginChallenge.objects.create(
            clinic=clinic,
            client=membership.client,
            code_hash=make_password(code),
            magic_token_digest=magic_digest,
            expires_at=timezone.now()
            + timedelta(minutes=int(getattr(settings, "PORTAL_OTP_EXPIRE_MINUTES", 15))),
        )

        if getattr(settings, "PORTAL_OTP_EMAIL_ENABLED", False):
            if sendgrid_configured():
                try:
                    send_portal_otp_email(
                        to_email=membership.client.email,
                        code=code,
                        clinic_name=clinic.name,
                        magic_link_url=magic_url,
                        magic_plain_token=magic_plain if not magic_url else None,
                    )
                except Exception:
                    logger.exception(
                        "portal_otp_email_send_failed clinic_id=%s client_id=%s",
                        clinic.id,
                        membership.client_id,
                    )
            else:
                logger.warning(
                    "PORTAL_OTP_EMAIL_ENABLED but SendGrid is not configured "
                    "(set REMINDER_SENDGRID_API_KEY and REMINDER_SENDGRID_FROM_EMAIL)."
                )

        payload = dict(generic)
        if getattr(settings, "PORTAL_RETURN_OTP_IN_RESPONSE", False):
            payload["_dev_otp"] = code
            payload["_dev_magic_link_token"] = magic_plain
        return Response(payload, status=200)


class PortalAuthMagicLinkView(APIView):
    """
    POST /api/portal/auth/magic-link/
    Body: { "token": "<plaintext from email or dev response>" } → same access JWT as confirm-code.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        token = (request.data.get("token") or "").strip()
        if not token:
            return Response({"detail": "token is required."}, status=400)

        ip = client_ip_from_request(request)
        if rate_limit_exceeded(
            portal_magic_link_ip_key(ip),
            int(getattr(settings, "PORTAL_MAGIC_LINK_LIMIT_PER_IP", 60)),
            int(getattr(settings, "PORTAL_MAGIC_LINK_IP_WINDOW_SEC", 900)),
        ):
            return Response(
                {"detail": "Too many requests. Please try again later."},
                status=429,
            )

        digest = digest_magic_token(token)
        now = timezone.now()
        err_resp: Response | None = None
        consumed_challenge: PortalLoginChallenge | None = None
        with transaction.atomic():
            ch = (
                PortalLoginChallenge.objects.select_for_update()
                .filter(
                    magic_token_digest=digest,
                    consumed_at__isnull=True,
                    expires_at__gte=now,
                )
                .select_related("clinic", "client")
                .first()
            )
            if not ch:
                err_resp = Response(
                    {"detail": "Invalid or expired sign-in link."},
                    status=400,
                )
            elif not ch.clinic.online_booking_enabled:
                err_resp = Response(
                    {"detail": "Online booking is disabled for this clinic."},
                    status=403,
                )
            elif not ClientClinic.objects.filter(
                clinic=ch.clinic,
                client=ch.client,
                is_active=True,
            ).exists():
                err_resp = Response(
                    {"detail": "Invalid or expired sign-in link."},
                    status=400,
                )
            else:
                ch.consumed_at = now
                ch.save(update_fields=["consumed_at"])
                consumed_challenge = ch

        if err_resp is not None:
            return err_resp
        assert consumed_challenge is not None
        clear_portal_confirm_failures(
            consumed_challenge.clinic.slug,
            (consumed_challenge.client.email or "").strip().lower(),
            ip,
        )
        access = create_portal_access_token(
            client_id=consumed_challenge.client_id,
            clinic_id=consumed_challenge.clinic_id,
        )
        return Response({"access": access})


class PortalAuthConfirmCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        slug = (request.data.get("clinic_slug") or "").strip()
        email = (request.data.get("email") or "").strip().lower()
        code = (request.data.get("code") or "").strip()
        if not slug or not email or not code:
            return Response(
                {"detail": "clinic_slug, email, and code are required."},
                status=400,
            )
        ip = client_ip_from_request(request)
        if is_portal_confirm_blocked(slug, email, ip):
            return Response(
                {"detail": "Too many invalid code attempts. Please try again later."},
                status=429,
            )
        if rate_limit_exceeded(
            portal_confirm_ip_key(ip),
            int(getattr(settings, "PORTAL_OTP_CONFIRM_LIMIT_PER_IP", 80)),
            int(getattr(settings, "PORTAL_OTP_CONFIRM_IP_WINDOW_SEC", 900)),
        ):
            return Response(
                {"detail": "Too many requests. Please try again later."},
                status=429,
            )
        if rate_limit_exceeded(
            portal_confirm_mailbox_key(slug, email),
            int(getattr(settings, "PORTAL_OTP_CONFIRM_LIMIT_PER_MAILBOX", 30)),
            int(getattr(settings, "PORTAL_OTP_CONFIRM_MAILBOX_WINDOW_SEC", 900)),
        ):
            return Response(
                {"detail": "Too many requests. Please try again later."},
                status=429,
            )

        err, clinic = _public_clinic_or_404(slug)
        if err:
            return err

        membership = (
            ClientClinic.objects.filter(
                clinic=clinic,
                is_active=True,
                client__email__iexact=email,
            )
            .select_related("client")
            .first()
        )
        if not membership:
            return Response({"detail": "Invalid or expired code."}, status=400)

        now = timezone.now()
        challenge = (
            PortalLoginChallenge.objects.filter(
                clinic=clinic,
                client=membership.client,
                consumed_at__isnull=True,
                expires_at__gte=now,
            )
            .order_by("-created_at")
            .first()
        )
        if not challenge or not check_password(code, challenge.code_hash):
            record_portal_confirm_failure(slug, email, ip)
            return Response({"detail": "Invalid or expired code."}, status=400)

        challenge.consumed_at = now
        challenge.save(update_fields=["consumed_at"])
        clear_portal_confirm_failures(slug, email, ip)

        access = create_portal_access_token(
            client_id=membership.client_id,
            clinic_id=clinic.id,
        )
        return Response({"access": access})


class PortalMePatientsView(APIView):
    permission_classes = [IsPortalClient]

    def get(self, request):
        assert isinstance(request.user, PortalPrincipal)
        p = request.user
        patients = Patient.objects.filter(
            clinic_id=p.portal_clinic_id,
            owner_id=p.client_id,
        ).order_by("name", "id")
        data = [
            {
                "id": pt.id,
                "name": pt.name,
                "species": pt.species,
                "breed": pt.breed,
            }
            for pt in patients
        ]
        return Response(data)


class PortalPatientDetailView(APIView):
    """
    GET /api/portal/me/patients/<patient_id>/
    Owner-facing pet card: demographics, upcoming visits, recent vaccinations, last recorded weight.
    """

    permission_classes = [IsPortalClient]

    def get(self, request, patient_id: int):
        assert isinstance(request.user, PortalPrincipal)
        p = request.user

        patient = (
            Patient.objects.filter(
                id=patient_id,
                clinic_id=p.portal_clinic_id,
                owner_id=p.client_id,
            )
            .select_related("primary_vet")
            .first()
        )
        if not patient:
            return Response({"detail": "Patient not found."}, status=404)

        pv = patient.primary_vet
        patient_payload = {
            "id": patient.id,
            "name": patient.name,
            "species": patient.species,
            "breed": patient.breed,
            "sex": patient.sex,
            "birth_date": patient.birth_date.isoformat() if patient.birth_date else None,
            "microchip_no": patient.microchip_no,
            "allergies": patient.allergies,
            "primary_vet_id": patient.primary_vet_id,
            "primary_vet_name": (pv.get_full_name() or pv.username) if pv else "",
        }

        tz = timezone.get_current_timezone()
        start_of_today = timezone.make_aware(
            datetime.combine(timezone.localdate(), dt_time.min),
            tz,
        )
        upcoming = (
            Appointment.objects.filter(
                clinic_id=p.portal_clinic_id,
                patient_id=patient.id,
                starts_at__gte=start_of_today,
            )
            .exclude(status=Appointment.Status.CANCELLED)
            .select_related("vet")
            .order_by("starts_at")[:25]
        )
        upcoming_payload = [
            {
                "id": a.id,
                "starts_at": a.starts_at.isoformat(),
                "ends_at": a.ends_at.isoformat(),
                "status": a.status,
                "reason": a.reason,
                "vet_id": a.vet_id,
                "vet_name": (a.vet.get_full_name() or a.vet.username) if a.vet_id else "",
            }
            for a in upcoming
        ]

        vaccinations = Vaccination.objects.filter(
            clinic_id=p.portal_clinic_id,
            patient_id=patient.id,
        ).order_by("-administered_at", "-id")[:15]
        vaccination_payload = [
            {
                "id": v.id,
                "vaccine_name": v.vaccine_name,
                "batch_number": v.batch_number,
                "administered_at": v.administered_at.isoformat(),
                "next_due_at": v.next_due_at.isoformat() if v.next_due_at else None,
                "notes": v.notes,
            }
            for v in vaccinations
        ]

        last_exam = (
            ClinicalExam.objects.filter(
                clinic_id=p.portal_clinic_id,
                appointment__patient_id=patient.id,
                appointment__status=Appointment.Status.COMPLETED,
                weight_kg__isnull=False,
            )
            .select_related("appointment")
            .order_by("-appointment__starts_at")
            .first()
        )
        last_weight = None
        last_weight_recorded_at = None
        if last_exam and last_exam.weight_kg is not None:
            last_weight = float(last_exam.weight_kg)
            last_weight_recorded_at = last_exam.appointment.starts_at.isoformat()

        return Response(
            {
                "patient": patient_payload,
                "upcoming_appointments": upcoming_payload,
                "recent_vaccinations": vaccination_payload,
                "last_weight_kg": last_weight,
                "last_weight_recorded_at": last_weight_recorded_at,
            },
        )


class PortalAvailabilityView(APIView):
    permission_classes = [IsPortalClient]

    def get(self, request):
        assert isinstance(request.user, PortalPrincipal)
        p = request.user
        clinic = Clinic.objects.filter(id=p.portal_clinic_id, online_booking_enabled=True).first()
        if not clinic:
            return Response({"detail": "Online booking is disabled."}, status=403)

        date_str = request.query_params.get("date")
        if not date_str:
            return Response({"detail": "Missing query param: date=YYYY-MM-DD"}, status=400)
        vet_raw = request.query_params.get("vet")
        vet_id = int(vet_raw) if vet_raw else None
        if vet_id is not None:
            if (
                not User.objects.filter(
                    id=vet_id,
                    clinic_id=clinic.id,
                )
                .filter(Q(role=User.Role.DOCTOR) | Q(is_vet=True))
                .exists()
            ):
                return Response({"detail": "Vet not found."}, status=404)
        room_raw = request.query_params.get("room")
        room_id = int(room_raw) if room_raw else None
        return Response(
            _dump_public_availability(clinic.id, date_str, vet_id, room_id),
        )


class PortalAppointmentListCreateView(APIView):
    permission_classes = [IsPortalClient]

    def get(self, request):
        assert isinstance(request.user, PortalPrincipal)
        p = request.user
        tz = timezone.get_current_timezone()
        start_of_today = timezone.make_aware(
            datetime.combine(timezone.localdate(), dt_time.min),
            tz,
        )
        appts = (
            Appointment.objects.filter(
                clinic_id=p.portal_clinic_id,
                patient__owner_id=p.client_id,
                starts_at__gte=start_of_today,
            )
            .exclude(status=Appointment.Status.CANCELLED)
            .select_related("patient", "vet", "portal_deposit_invoice")
            .order_by("starts_at")
        )
        data = []
        for a in appts:
            inv = a.portal_deposit_invoice
            row = {
                "id": a.id,
                "starts_at": a.starts_at.isoformat(),
                "ends_at": a.ends_at.isoformat(),
                "status": a.status,
                "reason": a.reason,
                "vet_id": a.vet_id,
                "vet_name": (a.vet.get_full_name() or a.vet.username) if a.vet_id else "",
                "patient_id": a.patient_id,
                "patient_name": a.patient.name,
                "deposit_invoice_id": inv.id if inv else None,
                "payment_required": bool(inv and inv.status != Invoice.Status.PAID),
            }
            data.append(row)
        return Response(data)

    def post(self, request):
        assert isinstance(request.user, PortalPrincipal)
        p = request.user
        clinic = Clinic.objects.filter(id=p.portal_clinic_id, online_booking_enabled=True).first()
        if not clinic:
            return Response({"detail": "Online booking is disabled."}, status=403)

        patient_id = request.data.get("patient_id")
        vet_id = request.data.get("vet_id")
        starts_at_raw = request.data.get("starts_at")
        ends_at_raw = request.data.get("ends_at")
        reason = (request.data.get("reason") or "")[:255]
        room_id_raw = request.data.get("room_id")

        if not patient_id or not vet_id or not starts_at_raw or not ends_at_raw:
            return Response(
                {"detail": "patient_id, vet_id, starts_at, and ends_at are required."},
                status=400,
            )

        try:
            patient_id = int(patient_id)
            vet_id = int(vet_id)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid patient_id or vet_id."}, status=400)

        room_id: int | None
        try:
            room_id = int(room_id_raw) if room_id_raw not in (None, "") else None
        except (TypeError, ValueError):
            return Response({"detail": "Invalid room_id."}, status=400)

        patient = Patient.objects.filter(
            id=patient_id,
            clinic_id=clinic.id,
            owner_id=p.client_id,
        ).first()
        if not patient:
            return Response({"detail": "Patient not found."}, status=404)

        if (
            not User.objects.filter(
                id=vet_id,
                clinic_id=clinic.id,
            )
            .filter(Q(role=User.Role.DOCTOR) | Q(is_vet=True))
            .exists()
        ):
            return Response({"detail": "Vet not found."}, status=404)

        if (
            room_id is not None
            and not Room.objects.filter(
                id=room_id,
                clinic_id=clinic.id,
            ).exists()
        ):
            return Response({"detail": "Room not found."}, status=404)

        starts_at = parse_datetime(starts_at_raw)
        ends_at = parse_datetime(ends_at_raw)
        if not starts_at or not ends_at:
            return Response(
                {"detail": "Invalid datetime format for starts_at/ends_at."}, status=400
            )

        if not portal_slot_matches_availability(
            clinic_id=clinic.id,
            vet_id=vet_id,
            room_id=room_id,
            starts_at=starts_at,
            ends_at=ends_at,
        ):
            return Response(
                {"detail": "Selected time is no longer available."},
                status=409,
            )

        deposit_amt = clinic.portal_booking_deposit_amount or Decimal("0")
        needs_deposit = deposit_amt > 0
        initial_status = (
            Appointment.Status.SCHEDULED if needs_deposit else Appointment.Status.CONFIRMED
        )

        with transaction.atomic():
            appt = Appointment(
                clinic=clinic,
                patient=patient,
                vet_id=vet_id,
                room_id=room_id,
                starts_at=starts_at,
                ends_at=ends_at,
                visit_type=Appointment.VisitType.OUTPATIENT,
                status=initial_status,
                reason=reason,
                booked_via_portal=True,
            )
            appt.save()
            patient.ai_summary = ""
            patient.ai_summary_updated_at = None
            patient.save(update_fields=["ai_summary", "ai_summary_updated_at"])

            deposit_invoice = None
            if needs_deposit:
                deposit_invoice = Invoice.objects.create(
                    clinic=clinic,
                    client=patient.owner,
                    patient=patient,
                    appointment=appt,
                    status=Invoice.Status.DRAFT,
                    currency="PLN",
                    created_by=None,
                )
                line_label = (
                    clinic.portal_booking_deposit_line_label or "Online booking deposit"
                ).strip() or "Online booking deposit"
                InvoiceLine.objects.create(
                    invoice=deposit_invoice,
                    description=line_label[:255],
                    quantity=Decimal("1"),
                    unit_price=deposit_amt,
                    vat_rate=InvoiceLine.VatRate.RATE_8,
                )
                appt.portal_deposit_invoice = deposit_invoice
                appt.save(update_fields=["portal_deposit_invoice", "updated_at"])

        log_audit_event(
            clinic_id=clinic.id,
            actor=None,
            action="portal_appointment_booked",
            entity_type="appointment",
            entity_id=appt.id,
            after={
                "patient_id": patient.id,
                "vet_id": vet_id,
                "starts_at": starts_at.isoformat(),
                "ends_at": ends_at.isoformat(),
                "client_id": p.client_id,
                "needs_deposit": needs_deposit,
                "deposit_invoice_id": deposit_invoice.id if deposit_invoice else None,
            },
            metadata={"source": "portal"},
        )

        notify_staff_new_portal_booking(
            clinic_id=clinic.id,
            patient_name=patient.name,
            appointment_id=appt.id,
            vet_id=vet_id,
            starts_at=starts_at,
        )

        if deposit_invoice:
            deposit_invoice = (
                Invoice.objects.filter(pk=deposit_invoice.pk).prefetch_related("lines").get()
            )
        return Response(
            _portal_appointment_booking_payload(appt, deposit_invoice),
            status=201,
        )


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

        appt, inv, err = _portal_deposit_lookup(p, invoice_id)
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
                        _portal_appointment_booking_payload(appt_done, inv_done), status=200
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
                _portal_appointment_booking_payload(outcome.appointment, outcome.invoice),
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
                _portal_appointment_booking_payload(appt_done, inv_done),
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

        appt, inv, err = _portal_deposit_lookup(p, invoice_id)
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


class PortalAppointmentCancelView(APIView):
    permission_classes = [IsPortalClient]

    def post(self, request, pk: int):
        assert isinstance(request.user, PortalPrincipal)
        p = request.user
        reason = (request.data.get("cancellation_reason") or "")[:255]

        appt = (
            Appointment.objects.filter(
                id=pk,
                clinic_id=p.portal_clinic_id,
                patient__owner_id=p.client_id,
            )
            .exclude(
                status__in=[Appointment.Status.CANCELLED, Appointment.Status.COMPLETED],
            )
            .first()
        )
        if not appt:
            return Response({"detail": "Appointment not found."}, status=404)

        old_status = appt.status
        with transaction.atomic():
            if appt.portal_deposit_invoice_id:
                inv = (
                    Invoice.objects.select_for_update()
                    .filter(pk=appt.portal_deposit_invoice_id)
                    .first()
                )
                if inv and inv.status == Invoice.Status.DRAFT:
                    inv.status = Invoice.Status.CANCELLED
                    inv.save(update_fields=["status", "updated_at"])
            appt.status = Appointment.Status.CANCELLED
            appt.cancelled_by = Appointment.CancelledBy.CLIENT
            appt.cancellation_reason = reason
            appt.cancelled_at = timezone.now()
            appt.save()

        log_audit_event(
            clinic_id=appt.clinic_id,
            actor=None,
            action="portal_appointment_cancelled",
            entity_type="appointment",
            entity_id=appt.id,
            before={"status": old_status},
            after={"status": appt.status},
            metadata={"client_id": p.client_id, "source": "portal"},
        )

        return Response(status=204)
