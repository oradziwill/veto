from __future__ import annotations

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import HasClinic, IsAdminOrReadOnly, IsClinicAdmin
from apps.scheduling.models_clinic_hours import ClinicWorkingHours
from apps.scheduling.models_duty import DutyAssignment
from apps.scheduling.models_exceptions import VetAvailabilityException
from apps.scheduling.models_working_hours import VetWorkingHours
from apps.scheduling.serializers_schedule import (
    ClinicHolidaySerializer,
    ClinicWorkingHoursSerializer,
    DutyAssignmentSerializer,
    VetAvailabilityExceptionSerializer,
    VetWorkingHoursSerializer,
)
from apps.scheduling.services.schedule_generator import generate_schedule
from apps.tenancy.models import ClinicHoliday


class VetWorkingHoursViewSet(viewsets.ModelViewSet):
    """
    Working hours per vet and weekday.
    All clinic staff can read. Only admins can write.
    Filter: ?vet=<id>
    """

    permission_classes = [IsAuthenticated, HasClinic, IsAdminOrReadOnly]
    serializer_class = VetWorkingHoursSerializer

    def get_queryset(self):
        qs = (
            VetWorkingHours.objects.filter(vet__clinic=self.request.user.clinic)
            .select_related("vet")
            .order_by("vet_id", "weekday", "start_time")
        )

        vet_id = self.request.query_params.get("vet")
        if vet_id:
            qs = qs.filter(vet_id=vet_id)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vet = serializer.validated_data["vet"]
        if vet.clinic_id != request.user.clinic_id:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Vet does not belong to your clinic.")
        weekday = serializer.validated_data["weekday"]
        obj, _ = VetWorkingHours.objects.update_or_create(
            vet=vet,
            weekday=weekday,
            defaults={
                "start_time": serializer.validated_data["start_time"],
                "end_time": serializer.validated_data["end_time"],
                "is_active": serializer.validated_data.get("is_active", True),
            },
        )
        return Response(self.get_serializer(obj).data, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        vet = serializer.validated_data["vet"]
        if vet.clinic_id != self.request.user.clinic_id:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Vet does not belong to your clinic.")
        serializer.save()


class VetAvailabilityExceptionViewSet(viewsets.ModelViewSet):
    """
    One-off overrides: day offs and custom hours for a vet on a specific date.
    All clinic staff can read. Only admins can write.
    Filters: ?vet=<id>, ?from=YYYY-MM-DD, ?to=YYYY-MM-DD
    """

    permission_classes = [IsAuthenticated, HasClinic, IsAdminOrReadOnly]
    serializer_class = VetAvailabilityExceptionSerializer

    def get_queryset(self):
        qs = (
            VetAvailabilityException.objects.filter(clinic=self.request.user.clinic)
            .select_related("vet")
            .order_by("date", "vet_id")
        )

        vet_id = self.request.query_params.get("vet")
        from_date = self.request.query_params.get("from")
        to_date = self.request.query_params.get("to")

        if vet_id:
            qs = qs.filter(vet_id=vet_id)
        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)
        return qs

    def perform_create(self, serializer):
        vet = serializer.validated_data["vet"]
        if vet.clinic_id != self.request.user.clinic_id:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Vet does not belong to your clinic.")
        serializer.save(clinic=self.request.user.clinic)

    def perform_update(self, serializer):
        serializer.save(clinic=self.request.user.clinic)


class ClinicHolidayViewSet(viewsets.ModelViewSet):
    """
    Clinic-wide closure dates (holidays, emergencies).
    All clinic staff can read. Only admins can write.
    """

    permission_classes = [IsAuthenticated, HasClinic, IsAdminOrReadOnly]
    serializer_class = ClinicHolidaySerializer

    def get_queryset(self):
        return ClinicHoliday.objects.filter(clinic=self.request.user.clinic).order_by("-date")

    def perform_create(self, serializer):
        serializer.save(clinic=self.request.user.clinic)


class ClinicWorkingHoursViewSet(viewsets.ModelViewSet):
    """
    Clinic open hours per weekday.
    All staff can read. Only admins can write.
    """

    permission_classes = [IsAuthenticated, HasClinic, IsAdminOrReadOnly]
    serializer_class = ClinicWorkingHoursSerializer

    def get_queryset(self):
        return ClinicWorkingHours.objects.filter(clinic=self.request.user.clinic).order_by(
            "weekday"
        )

    def perform_create(self, serializer):
        serializer.save(clinic=self.request.user.clinic)

    def perform_update(self, serializer):
        serializer.save(clinic=self.request.user.clinic)


class DutyAssignmentViewSet(viewsets.ModelViewSet):
    """
    Duty assignments — who covers the clinic on a given date.
    Filters: ?from=YYYY-MM-DD, ?to=YYYY-MM-DD, ?vet=<id>
    """

    permission_classes = [IsAuthenticated, HasClinic, IsAdminOrReadOnly]
    serializer_class = DutyAssignmentSerializer

    def get_queryset(self):
        qs = (
            DutyAssignment.objects.filter(clinic=self.request.user.clinic)
            .select_related("vet")
            .order_by("date", "start_time")
        )

        from_date = self.request.query_params.get("from")
        to_date = self.request.query_params.get("to")
        vet_id = self.request.query_params.get("vet")

        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)
        if vet_id:
            qs = qs.filter(vet_id=vet_id)
        return qs

    def perform_create(self, serializer):
        vet = serializer.validated_data["vet"]
        if vet.clinic_id != self.request.user.clinic_id:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Vet does not belong to your clinic.")
        serializer.save(clinic=self.request.user.clinic, is_auto_generated=False)


class GenerateScheduleView(APIView):
    """
    POST /api/schedule/generate/
    Body: { start_date, end_date, overwrite (bool, default false) }
    Generates duty assignments using fair rotation algorithm.
    Only clinic admins can call this.
    """

    permission_classes = [IsAuthenticated, HasClinic, IsClinicAdmin]

    def post(self, request):
        start_str = request.data.get("start_date")
        end_str = request.data.get("end_date")
        overwrite = bool(request.data.get("overwrite", False))

        if not start_str or not end_str:
            return Response(
                {"detail": "start_date and end_date are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from django.utils.dateparse import parse_date

            start_date = parse_date(start_str)
            end_date = parse_date(end_str)
            if not start_date or not end_date:
                raise ValueError
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if end_date < start_date:
            return Response(
                {"detail": "end_date must be after start_date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        delta = (end_date - start_date).days
        if delta > 400:
            return Response(
                {"detail": "Date range cannot exceed 400 days."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        clinic = request.user.clinic
        doctors = User.objects.filter(clinic=clinic, role="doctor")

        if not doctors.exists():
            return Response(
                {"detail": "No doctors found in this clinic."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = generate_schedule(clinic, start_date, end_date, doctors, overwrite=overwrite)
        return Response(result, status=status.HTTP_200_OK)
