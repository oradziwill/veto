from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsDoctorOrAdmin, IsStaffOrVet

from .models import Lab, LabOrder, LabOrderLine, LabResult, LabTest
from .serializers import (
    LabOrderReadSerializer,
    LabOrderWriteSerializer,
    LabResultSerializer,
    LabResultWriteSerializer,
    LabSerializer,
    LabTestSerializer,
)


class LabViewSet(viewsets.ModelViewSet):
    """Labs - in-clinic and external."""

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
    serializer_class = LabSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Lab.objects.filter(
            Q(clinic_id=user.clinic_id) | Q(clinic__isnull=True, lab_type="external")
        ).order_by("name")
        lab_type = self.request.query_params.get("lab_type")
        if lab_type:
            qs = qs.filter(lab_type=lab_type)
        return qs

    def perform_create(self, serializer):
        serializer.save(clinic_id=self.request.user.clinic_id)


class LabTestViewSet(viewsets.ModelViewSet):
    """Lab test catalog."""

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
    serializer_class = LabTestSerializer

    def get_queryset(self):
        user = self.request.user
        qs = (
            LabTest.objects.filter(
                Q(lab__clinic_id=user.clinic_id) | Q(lab__clinic__isnull=True) | Q(lab__isnull=True)
            )
            .select_related("lab")
            .order_by("name")
        )
        lab_id = self.request.query_params.get("lab")
        if lab_id:
            qs = qs.filter(lab_id=lab_id)
        return qs


class LabOrderViewSet(viewsets.ModelViewSet):
    """Lab orders - Doctor/Admin create, all staff can list."""

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        user = self.request.user
        qs = (
            LabOrder.objects.filter(clinic_id=user.clinic_id)
            .select_related("patient", "lab", "ordered_by", "appointment", "hospital_stay")
            .prefetch_related("lines__test", "lines__result")
            .order_by("-ordered_at")
        )
        patient_id = self.request.query_params.get("patient")
        status = self.request.query_params.get("status")
        if patient_id:
            qs = qs.filter(patient_id=patient_id)
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return LabOrderReadSerializer
        return LabOrderWriteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(
            LabOrderReadSerializer(order).data,
            status=201,
        )

    @action(detail=True, methods=["post"], url_path="send")
    def send_order(self, request, pk=None):
        """Mark order as sent to lab."""
        order = self.get_object()
        if order.status != "draft":
            return Response(
                {"detail": "Only draft orders can be sent."},
                status=400,
            )
        order.status = "sent"
        order.save(update_fields=["status"])
        return Response(LabOrderReadSerializer(order).data)

    @action(detail=True, methods=["post", "patch"], url_path="enter-result")
    def enter_result(self, request, pk=None):
        """
        POST/PATCH: Enter or update result for an order line.
        Body: { "order_line_id": <id>, "value": "...", "value_numeric": ..., "status": "completed", ... }
        Doctor/Admin only.
        """
        if not IsDoctorOrAdmin().has_permission(request, self):
            raise PermissionDenied("Only doctors and clinic admins can enter results.")

        order = self.get_object()
        line_id = request.data.get("order_line_id")
        if not line_id:
            return Response(
                {"order_line_id": ["This field is required."]},
                status=400,
            )
        try:
            line = order.lines.get(pk=line_id)
        except LabOrderLine.DoesNotExist:
            return Response({"detail": "Order line not found."}, status=404)

        result = getattr(line, "result", None)
        if not result:
            result = LabResult.objects.create(order_line=line)

        data = {k: v for k, v in request.data.items() if k != "order_line_id"}
        serializer = LabResultWriteSerializer(result, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        result = serializer.save(created_by=request.user)
        return Response(LabResultSerializer(result).data)
