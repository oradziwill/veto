from __future__ import annotations

from datetime import datetime
from datetime import time as dt_time
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.audit.services import log_audit_event
from apps.billing.models import Invoice, InvoiceLine
from apps.patients.models import Patient
from apps.scheduling.models import Appointment, Room
from apps.tenancy.models import Clinic

from .authentication import PortalPrincipal
from .permissions import IsPortalClient
from .services.booking import portal_slot_matches_availability
from .services.idempotency import run_idempotent_portal_post
from .services.staff_notify_booking import notify_staff_new_portal_booking
from .view_helpers import dump_public_availability, portal_appointment_booking_payload


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
            dump_public_availability(clinic.id, date_str, vet_id, room_id),
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

        deposit_amt = clinic.portal_booking_deposit_amount or Decimal("0")
        needs_deposit = deposit_amt > 0
        initial_status = (
            Appointment.Status.SCHEDULED if needs_deposit else Appointment.Status.CONFIRMED
        )

        payload_for_hash = {
            "patient_id": patient_id,
            "vet_id": vet_id,
            "room_id": room_id,
            "starts_at": starts_at_raw,
            "ends_at": ends_at_raw,
            "reason": reason,
        }

        def do_book():
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

            appt: Appointment | None = None
            deposit_invoice: Invoice | None = None
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

            assert appt is not None

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
                portal_appointment_booking_payload(appt, deposit_invoice),
                status=201,
            )

        return run_idempotent_portal_post(
            request=request,
            client_id=p.client_id,
            clinic_id=clinic.id,
            operation="portal_book_appointment",
            payload_for_hash=payload_for_hash,
            handler=do_book,
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
