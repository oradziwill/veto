from __future__ import annotations

from datetime import date as date_type

from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsDoctorOrAdmin, IsStaffOrVet
from apps.scheduling.models import Appointment, Room, WaitingQueueEntry
from apps.scheduling.serializers import (
    RoomSerializer,
    WaitingQueueEntryReadSerializer,
    WaitingQueueEntryWriteSerializer,
)
from apps.scheduling.services.availability import compute_availability
from apps.tenancy.access import accessible_clinic_ids, clinic_id_for_mutation


class RoomViewSet(viewsets.ReadOnlyModelViewSet):
    """List rooms for the user's clinic (for dropdowns and calendar). Manage rooms in Django admin."""

    permission_classes = [IsAuthenticated, HasClinic]
    serializer_class = RoomSerializer

    def get_queryset(self):
        return Room.objects.filter(clinic_id__in=accessible_clinic_ids(self.request.user)).order_by(
            "display_order", "name"
        )


class AvailabilityView(APIView):
    """
    Read-only endpoint returning available time slots for a given date.
    Optional vet-specific availability.
    """

    permission_classes = [IsAuthenticated, HasClinic]

    def get(self, request):
        user = request.user

        # ---- date validation (robust, no 500s) ----
        date_str = request.query_params.get("date")
        if not date_str:
            return Response(
                {"detail": "Missing required query param: date=YYYY-MM-DD"},
                status=400,
            )

        try:
            parsed_day: date_type | None = parse_date(date_str)
        except ValueError:
            parsed_day = None

        if parsed_day is None:
            return Response(
                {"detail": "Invalid date. Use YYYY-MM-DD (e.g., 2025-12-23)."},
                status=400,
            )

        # ---- optional params ----
        vet = request.query_params.get("vet")
        vet_id = int(vet) if vet else None

        room = request.query_params.get("room")
        room_id = int(room) if room else None

        slot = request.query_params.get("slot")
        slot_minutes = int(slot) if slot else None

        # ---- compute availability ----
        cid = clinic_id_for_mutation(user, request=request, instance_clinic_id=None)
        data = compute_availability(
            clinic_id=cid,
            date_str=date_str,
            vet_id=vet_id,
            room_id=room_id,
            slot_minutes=slot_minutes,
        )

        work_bounds = data.get("work_bounds")

        def dump_interval(interval):
            return {
                "start": interval.start.isoformat(),
                "end": interval.end.isoformat(),
            }

        return Response(
            {
                "date": date_str,
                "timezone": data["timezone"],
                "clinic_id": cid,
                "vet_id": vet_id,
                "room_id": room_id,
                "slot_minutes": data["slot_minutes"],
                "closed_reason": data.get("closed_reason"),
                "workday": dump_interval(work_bounds) if work_bounds else None,
                "work_intervals": [dump_interval(i) for i in data["work_intervals"]],
                "busy": [dump_interval(i) for i in data["busy_merged"]],
                "free": [dump_interval(i) for i in data["free_slots"]],
            }
        )


class AvailabilityRoomsView(APIView):
    """
    GET /availability/rooms/?date=YYYY-MM-DD
    Returns availability per room for the given date (for calendar room view).
    """

    permission_classes = [IsAuthenticated, HasClinic]

    def get(self, request):
        user = request.user
        date_str = request.query_params.get("date")
        if not date_str:
            return Response(
                {"detail": "Missing required query param: date=YYYY-MM-DD"},
                status=400,
            )
        try:
            parse_date(date_str)
        except ValueError:
            return Response(
                {"detail": "Invalid date. Use YYYY-MM-DD."},
                status=400,
            )

        rooms = Room.objects.filter(clinic_id__in=accessible_clinic_ids(user)).order_by(
            "display_order", "name"
        )
        slot_minutes = 30
        result = []

        def dump_interval(interval):
            return {
                "start": interval.start.isoformat(),
                "end": interval.end.isoformat(),
            }

        for room in rooms:
            data = compute_availability(
                clinic_id=room.clinic_id,
                date_str=date_str,
                vet_id=None,
                room_id=room.id,
                slot_minutes=slot_minutes,
            )
            result.append(
                {
                    "id": room.id,
                    "name": room.name,
                    "busy": [dump_interval(i) for i in data["busy_merged"]],
                    "free": [dump_interval(i) for i in data["free_slots"]],
                    "workday": (
                        dump_interval(data["work_bounds"]) if data.get("work_bounds") else None
                    ),
                    "closed_reason": data.get("closed_reason"),
                }
            )

        return Response({"date": date_str, "rooms": result})


class WaitingQueueViewSet(viewsets.ModelViewSet):
    """
    Walk-in patient queue. Receptionist/doctor adds patients; doctor calls them.
    List returns only active entries (waiting or in_progress).
    """

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        return (
            WaitingQueueEntry.objects.filter(
                clinic_id__in=accessible_clinic_ids(self.request.user),
                status__in=[
                    WaitingQueueEntry.Status.WAITING,
                    WaitingQueueEntry.Status.IN_PROGRESS,
                ],
            )
            .select_related("patient", "patient__owner", "called_by")
            .order_by("position", "arrived_at")
        )

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return WaitingQueueEntryReadSerializer
        return WaitingQueueEntryWriteSerializer

    def perform_create(self, serializer):
        clinic_id = clinic_id_for_mutation(
            self.request.user, request=self.request, instance_clinic_id=None
        )
        max_pos = (
            WaitingQueueEntry.objects.filter(
                clinic_id=clinic_id,
                status__in=[
                    WaitingQueueEntry.Status.WAITING,
                    WaitingQueueEntry.Status.IN_PROGRESS,
                ],
            ).aggregate(m=models.Max("position"))["m"]
            or 0
        )
        serializer.save(clinic_id=clinic_id, position=max_pos + 1)

    @action(detail=False, methods=["post"], url_path="register-incoming")
    def register_incoming(self, request):
        patient_id = request.data.get("patient")
        chief_complaint = request.data.get("chief_complaint", "")
        is_urgent = bool(request.data.get("is_urgent", False))
        appointment_id = request.data.get("appointment_id")

        if not patient_id:
            return Response({"detail": "patient is required."}, status=400)

        clinic_id = clinic_id_for_mutation(
            request.user, request=request, instance_clinic_id=None
        )

        today = timezone.localdate()
        if appointment_id:
            appointment = Appointment.objects.filter(
                id=appointment_id,
                clinic_id=clinic_id,
                patient_id=patient_id,
                status__in=[Appointment.Status.SCHEDULED, Appointment.Status.CONFIRMED],
            ).first()
        else:
            appointment = (
                Appointment.objects.filter(
                    clinic_id=clinic_id,
                    patient_id=patient_id,
                    starts_at__date=today,
                    status__in=[Appointment.Status.SCHEDULED, Appointment.Status.CONFIRMED],
                )
                .order_by("starts_at")
                .first()
            )

        max_pos = (
            WaitingQueueEntry.objects.filter(
                clinic_id=clinic_id,
                status__in=[
                    WaitingQueueEntry.Status.WAITING,
                    WaitingQueueEntry.Status.IN_PROGRESS,
                ],
            ).aggregate(m=models.Max("position"))["m"]
            or 0
        )

        entry_kwargs = dict(
            clinic_id=clinic_id,
            patient_id=patient_id,
            chief_complaint=chief_complaint,
            is_urgent=is_urgent,
            position=max_pos + 1,
        )
        if appointment:
            already_queued = WaitingQueueEntry.objects.filter(
                appointment=appointment,
                status__in=[
                    WaitingQueueEntry.Status.WAITING,
                    WaitingQueueEntry.Status.IN_PROGRESS,
                ],
            ).exists()
            if not already_queued:
                entry_kwargs["appointment"] = appointment
                appointment.status = Appointment.Status.CHECKED_IN
                appointment.save(update_fields=["status", "updated_at"])

        entry = WaitingQueueEntry.objects.create(**entry_kwargs)
        data = WaitingQueueEntryReadSerializer(entry).data
        data["appointment_matched"] = appointment is not None and "appointment" in entry_kwargs
        return Response(data, status=201)

    @action(detail=True, methods=["post"], url_path="move-up")
    def move_up(self, request, pk=None):
        entry = self.get_object()
        above = (
            WaitingQueueEntry.objects.filter(
                clinic_id=entry.clinic_id,
                status__in=[
                    WaitingQueueEntry.Status.WAITING,
                    WaitingQueueEntry.Status.IN_PROGRESS,
                ],
                position__lt=entry.position,
            )
            .order_by("-position")
            .first()
        )
        if above:
            entry.position, above.position = above.position, entry.position
            entry.save(update_fields=["position"])
            above.save(update_fields=["position"])
        return Response(WaitingQueueEntryReadSerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="move-down")
    def move_down(self, request, pk=None):
        entry = self.get_object()
        below = (
            WaitingQueueEntry.objects.filter(
                clinic_id=entry.clinic_id,
                status__in=[
                    WaitingQueueEntry.Status.WAITING,
                    WaitingQueueEntry.Status.IN_PROGRESS,
                ],
                position__gt=entry.position,
            )
            .order_by("position")
            .first()
        )
        if below:
            entry.position, below.position = below.position, entry.position
            entry.save(update_fields=["position"])
            below.save(update_fields=["position"])
        return Response(WaitingQueueEntryReadSerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="call")
    def call(self, request, pk=None):
        if not IsDoctorOrAdmin().has_permission(request, self):
            raise PermissionDenied("Only doctors and clinic admins can call a patient.")
        entry = self.get_object()
        if entry.status != WaitingQueueEntry.Status.WAITING:
            return Response({"detail": "Entry is not in waiting status."}, status=400)

        already_active = WaitingQueueEntry.objects.filter(
            clinic_id=entry.clinic_id,
            called_by=request.user,
            status=WaitingQueueEntry.Status.IN_PROGRESS,
        ).exists()
        if already_active:
            return Response(
                {
                    "detail": "You already have a patient in progress. Close the current visit first."
                },
                status=409,
            )

        entry.status = WaitingQueueEntry.Status.IN_PROGRESS
        entry.called_by = request.user
        entry.save(update_fields=["status", "called_by"])

        return Response(WaitingQueueEntryReadSerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="requeue")
    def requeue(self, request, pk=None):
        if not IsDoctorOrAdmin().has_permission(request, self):
            raise PermissionDenied("Only doctors and clinic admins can requeue a patient.")
        entry = self.get_object()
        if entry.status != WaitingQueueEntry.Status.IN_PROGRESS:
            return Response({"detail": "Entry is not in progress."}, status=400)
        entry.status = WaitingQueueEntry.Status.WAITING
        entry.called_by = None
        entry.save(update_fields=["status", "called_by"])
        return Response(WaitingQueueEntryReadSerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="done")
    def done(self, request, pk=None):
        if not IsDoctorOrAdmin().has_permission(request, self):
            raise PermissionDenied("Only doctors and clinic admins can mark a visit as done.")
        entry = self.get_object()
        entry.status = WaitingQueueEntry.Status.DONE
        entry.save(update_fields=["status"])
        return Response(status=204)
