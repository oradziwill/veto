from __future__ import annotations

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClinicalProcedure, VisitProcedureSession
from .serializers import (
    ClinicalProcedureDetailSerializer,
    ClinicalProcedureListSerializer,
    VisitProcedureSessionSerializer,
)


class ClinicalProcedureViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    lookup_field = "slug"

    def get_queryset(self):
        return ClinicalProcedure.objects.filter(is_active=True)

    def list(self, request, *args, **kwargs):
        qs = list(self.get_queryset())
        species = request.query_params.get("species")
        if species:
            qs = [p for p in qs if species in (p.species or [])]
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ClinicalProcedureDetailSerializer
        return ClinicalProcedureListSerializer


class VisitProcedureSessionViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = VisitProcedureSessionSerializer

    def get_queryset(self):
        appointment_id = self.kwargs.get("appointment_pk")
        if appointment_id:
            return VisitProcedureSession.objects.filter(appointment_id=appointment_id)
        return VisitProcedureSession.objects.filter(doctor=self.request.user)

    def perform_create(self, serializer):
        appointment_id = self.kwargs.get("appointment_pk")
        serializer.save(
            doctor=self.request.user,
            appointment_id=appointment_id,
        )
