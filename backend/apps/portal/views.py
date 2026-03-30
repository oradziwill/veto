from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta
from datetime import time as dt_time

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.audit.services import log_audit_event
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
from .tokens import create_portal_access_token


def _generate_portal_code() -> str:
    digits = string.digits
    return "".join(secrets.choice(digits) for _ in range(6))


def _get_clinic_by_slug(slug: str) -> Clinic | None:
    return (
        Clinic.objects.filter(slug=slug)
        .only("id", "slug", "name", "online_booking_enabled")
        .first()
    )


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
        PortalLoginChallenge.objects.create(
            clinic=clinic,
            client=membership.client,
            code_hash=make_password(code),
            expires_at=timezone.now()
            + timedelta(minutes=int(getattr(settings, "PORTAL_OTP_EXPIRE_MINUTES", 15))),
        )

        payload = dict(generic)
        if getattr(settings, "PORTAL_RETURN_OTP_IN_RESPONSE", False):
            payload["_dev_otp"] = code
        return Response(payload, status=200)


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
            return Response({"detail": "Invalid or expired code."}, status=400)

        challenge.consumed_at = now
        challenge.save(update_fields=["consumed_at"])

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
            .select_related("patient", "vet")
            .order_by("starts_at")
        )
        data = [
            {
                "id": a.id,
                "starts_at": a.starts_at.isoformat(),
                "ends_at": a.ends_at.isoformat(),
                "status": a.status,
                "reason": a.reason,
                "vet_id": a.vet_id,
                "vet_name": (a.vet.get_full_name() or a.vet.username) if a.vet_id else "",
                "patient_id": a.patient_id,
                "patient_name": a.patient.name,
            }
            for a in appts
        ]
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

        appt = Appointment(
            clinic=clinic,
            patient=patient,
            vet_id=vet_id,
            room_id=room_id,
            starts_at=starts_at,
            ends_at=ends_at,
            visit_type=Appointment.VisitType.OUTPATIENT,
            status=Appointment.Status.CONFIRMED,
            reason=reason,
        )
        appt.save()
        patient.ai_summary = ""
        patient.ai_summary_updated_at = None
        patient.save(update_fields=["ai_summary", "ai_summary_updated_at"])

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
            },
            metadata={"source": "portal"},
        )

        return Response(
            {
                "id": appt.id,
                "starts_at": appt.starts_at.isoformat(),
                "ends_at": appt.ends_at.isoformat(),
                "status": appt.status,
                "reason": appt.reason,
                "vet_id": appt.vet_id,
                "patient_id": appt.patient_id,
            },
            status=201,
        )


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
