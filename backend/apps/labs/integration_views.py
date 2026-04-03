from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsAdminOrReadOnly, IsDoctorOrAdmin, IsStaffOrVet

from .models import (
    LabIngestionEnvelope,
    LabIntegrationDevice,
    LabObservation,
    LabOrderLine,
    LabSample,
    LabTestCodeMap,
)
from .serializers import (
    LabIngestionEnvelopeSerializer,
    LabIntegrationDeviceSerializer,
    LabObservationSerializer,
    LabSampleReadSerializer,
    LabSampleWriteSerializer,
    LabTestCodeMapSerializer,
)
from .services.ingestion_pipeline import (
    create_envelope_and_process,
    process_lab_ingestion_envelope,
    verify_ingest_token,
)
from .services.materialization import materialize_lab_order, refresh_order_status_after_integration


class LabIntegrationDeviceViewSet(viewsets.ModelViewSet):
    """Configure analyzers / ingest endpoints (admin)."""

    permission_classes = [IsAuthenticated, HasClinic, IsAdminOrReadOnly]
    serializer_class = LabIntegrationDeviceSerializer

    def get_queryset(self):
        return LabIntegrationDevice.objects.filter(clinic_id=self.request.user.clinic_id).order_by(
            "name"
        )

    def perform_update(self, serializer):
        if (
            "ingest_token" not in serializer.validated_data
            and "ingest_token" not in self.request.data
        ):
            serializer.save()
            return
        if self.request.data.get("ingest_token") in (None, ""):
            inst = serializer.instance
            serializer.save(ingest_token=inst.ingest_token)
            return
        serializer.save()


class LabTestCodeMapViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsAdminOrReadOnly]
    serializer_class = LabTestCodeMapSerializer

    def get_queryset(self):
        return LabTestCodeMap.objects.filter(clinic_id=self.request.user.clinic_id).select_related(
            "lab_test",
            "device",
        )

    def perform_create(self, serializer):
        device = serializer.validated_data.get("device")
        if device and device.clinic_id != self.request.user.clinic_id:
            raise PermissionDenied("Device must belong to your clinic.")
        serializer.save(clinic_id=self.request.user.clinic_id)


class LabSampleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsDoctorOrAdmin]

    def get_queryset(self):
        return (
            LabSample.objects.filter(clinic_id=self.request.user.clinic_id)
            .select_related("lab_order")
            .prefetch_related("external_ids")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return LabSampleReadSerializer
        return LabSampleWriteSerializer


class LabIngestionEnvelopeViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
    serializer_class = LabIngestionEnvelopeSerializer

    def get_queryset(self):
        qs = LabIngestionEnvelope.objects.filter(clinic_id=self.request.user.clinic_id).order_by(
            "-received_at"
        )
        st = self.request.query_params.get("status")
        if st:
            qs = qs.filter(processing_status=st)
        return qs.select_related("device")

    def get_permissions(self):
        if self.action == "reprocess":
            return [IsAuthenticated(), HasClinic(), IsDoctorOrAdmin()]
        return [perm() for perm in self.permission_classes]

    @action(detail=True, methods=["post"], url_path="reprocess")
    def reprocess(self, request, pk=None):
        env = self.get_object()
        process_lab_ingestion_envelope(env.id)
        env.refresh_from_db()
        return Response(self.get_serializer(env).data)


class LabObservationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
    serializer_class = LabObservationSerializer

    def get_queryset(self):
        qs = LabObservation.objects.filter(clinic_id=self.request.user.clinic_id).select_related(
            "envelope",
            "device",
            "lab_order",
            "lab_order_line",
            "internal_test",
        )
        ms = self.request.query_params.get("match_status")
        if ms:
            qs = qs.filter(match_status=ms)
        return qs.order_by("-ingested_at")

    def get_permissions(self):
        if self.action == "resolve":
            return [IsAuthenticated(), HasClinic(), IsDoctorOrAdmin()]
        return [perm() for perm in self.permission_classes]

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, pk=None):
        obs = self.get_object()
        line_id = request.data.get("lab_order_line_id")
        if not line_id:
            return Response({"lab_order_line_id": ["required"]}, status=status.HTTP_400_BAD_REQUEST)
        line = get_object_or_404(
            LabOrderLine,
            pk=line_id,
            order__clinic_id=request.user.clinic_id,
        )
        obs.lab_order_line = line
        obs.lab_order = line.order
        obs.internal_test = line.test
        obs.match_status = LabObservation.MatchStatus.MATCHED
        obs.save(
            update_fields=[
                "lab_order_line",
                "lab_order",
                "internal_test",
                "match_status",
            ],
        )
        materialize_lab_order(line.order)
        refresh_order_status_after_integration(line.order)
        return Response(self.get_serializer(obs).data)


class LabDeviceIngestView(APIView):
    """Unauthenticated ingress secured with per-device ingest_token (X-Lab-Ingest-Token)."""

    permission_classes = [AllowAny]

    def post(self, request, device_id: int):
        device = get_object_or_404(
            LabIntegrationDevice,
            pk=device_id,
            is_active=True,
        )
        token = request.headers.get("X-Lab-Ingest-Token")
        if not verify_ingest_token(device, token):
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        raw = request.body or b""
        env, created = create_envelope_and_process(
            clinic_id=device.clinic_id, device=device, raw_bytes=raw
        )
        ser = LabIngestionEnvelopeSerializer(env, context={"request": request})
        return Response(
            {**ser.data, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
