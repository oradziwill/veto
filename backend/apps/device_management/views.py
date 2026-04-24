from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsAdminOrReadOnly, IsStaffOrVet
from apps.tenancy.access import accessible_clinic_ids, clinic_id_for_mutation

from .models import (
    AgentNode,
    DeviceCommand,
    DeviceEvent,
    FiscalReceipt,
    FiscalReceiptPrintAttempt,
)
from .serializers import (
    AgentHeartbeatSerializer,
    AgentRegisterSerializer,
    DeviceCommandResultSerializer,
    DeviceCommandSerializer,
    DeviceEventWriteSerializer,
    DeviceInventoryUpsertSerializer,
    DeviceSerializer,
    FiscalReceiptSerializer,
    queryset_for_user_devices,
)


class DeviceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
    serializer_class = DeviceSerializer

    def get_queryset(self):
        qs = (
            queryset_for_user_devices(self.request.user)
            .prefetch_related("capabilities")
            .order_by("name")
        )
        dtype = self.request.query_params.get("device_type")
        if dtype:
            qs = qs.filter(device_type=dtype)
        state = self.request.query_params.get("lifecycle_state")
        if state:
            qs = qs.filter(lifecycle_state=state)
        return qs


class AgentRegisterView(APIView):
    permission_classes = [IsAuthenticated, HasClinic]

    def post(self, request):
        serializer = AgentRegisterSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        agent = serializer.save()
        return Response(
            {
                "id": agent.id,
                "clinic_id": agent.clinic_id,
                "node_id": agent.node_id,
                "status": agent.status,
                "last_seen_at": agent.last_seen_at,
            },
            status=status.HTTP_201_CREATED,
        )


class AgentHeartbeatView(APIView):
    permission_classes = [IsAuthenticated, HasClinic]

    def post(self, request):
        serializer = AgentHeartbeatSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        hb = serializer.save()
        return Response(
            {
                "id": hb.id,
                "received_at": hb.received_at,
            },
            status=status.HTTP_201_CREATED,
        )


class DeviceInventoryUpsertView(APIView):
    permission_classes = [IsAuthenticated, HasClinic]

    def post(self, request):
        serializer = DeviceInventoryUpsertSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        rows = serializer.save()
        return Response({"upserted": len(rows)}, status=status.HTTP_200_OK)


class AgentCommandPullView(APIView):
    permission_classes = [IsAuthenticated, HasClinic]

    def get(self, request):
        cid = clinic_id_for_mutation(request.user, request=request, instance_clinic_id=None)
        node_id = request.query_params.get("node_id")
        if not node_id:
            return Response({"node_id": ["This query param is required."]}, status=400)
        agent = AgentNode.objects.filter(clinic_id=cid, node_id=node_id).first()
        if not agent:
            return Response({"detail": "Agent not registered."}, status=404)
        rows = (
            DeviceCommand.objects.filter(
                clinic_id=cid,
                status=DeviceCommand.CommandStatus.PENDING,
            )
            .filter(Q(agent__isnull=True) | Q(agent=agent))
            .order_by("created_at")[:20]
        )
        data = DeviceCommandSerializer(rows, many=True).data
        if rows:
            DeviceCommand.objects.filter(id__in=[r.id for r in rows]).update(
                status=DeviceCommand.CommandStatus.ACKED
            )
        agent.last_seen_at = timezone.now()
        agent.status = AgentNode.AgentStatus.ONLINE
        agent.save(update_fields=["last_seen_at", "status", "updated_at"])
        return Response(data)


class AgentCommandResultView(APIView):
    permission_classes = [IsAuthenticated, HasClinic]

    def post(self, request, command_id: int):
        cmd = DeviceCommand.objects.filter(
            pk=command_id,
            clinic_id__in=accessible_clinic_ids(request.user),
        ).first()
        if not cmd:
            return Response({"detail": "Not found."}, status=404)
        serializer = DeviceCommandResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        cmd.status = data["status"]
        cmd.result_payload = data.get("result_payload", {})
        cmd.error_message = data.get("error_message", "")
        cmd.executed_at = timezone.now()
        cmd.save(
            update_fields=["status", "result_payload", "error_message", "executed_at", "updated_at"]
        )
        if cmd.command_type == "fiscal_print":
            rid = cmd.payload.get("receipt_pk", cmd.payload.get("receipt_id"))
            try:
                rid_int = int(rid) if rid is not None else None
            except (TypeError, ValueError):
                rid_int = None
            if rid_int is None:
                return Response({"ok": True}, status=200)
            receipt = FiscalReceipt.objects.filter(pk=rid_int, clinic_id=cmd.clinic_id).first()
            if receipt:
                if cmd.status == DeviceCommand.CommandStatus.SUCCEEDED:
                    receipt.status = FiscalReceipt.Status.PRINTED
                    receipt.printed_at = timezone.now()
                    receipt.error_message = ""
                elif cmd.status == DeviceCommand.CommandStatus.FAILED:
                    receipt.status = FiscalReceipt.Status.FAILED
                    receipt.error_message = cmd.error_message[:512]
                else:
                    receipt.status = FiscalReceipt.Status.UNKNOWN
                receipt.save(update_fields=["status", "printed_at", "error_message", "updated_at"])
                last_no = (
                    receipt.attempts.order_by("-attempt_no")
                    .values_list("attempt_no", flat=True)
                    .first()
                    or 0
                )
                FiscalReceiptPrintAttempt.objects.create(
                    receipt=receipt,
                    command=cmd,
                    attempt_no=last_no + 1,
                    status=cmd.status,
                    message=cmd.error_message[:512],
                    payload=cmd.result_payload,
                )
        return Response({"ok": True}, status=200)


class DeviceEventViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
    serializer_class = DeviceEventWriteSerializer

    def get_queryset(self):
        return DeviceEvent.objects.filter(
            clinic_id__in=accessible_clinic_ids(self.request.user)
        ).order_by("-created_at")


class DeviceCommandAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsAdminOrReadOnly]
    serializer_class = DeviceCommandSerializer

    def get_queryset(self):
        return DeviceCommand.objects.filter(
            clinic_id__in=accessible_clinic_ids(self.request.user)
        ).order_by("-created_at")


class FiscalReceiptViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsAdminOrReadOnly]
    serializer_class = FiscalReceiptSerializer

    def get_queryset(self):
        return FiscalReceipt.objects.filter(
            clinic_id__in=accessible_clinic_ids(self.request.user)
        ).order_by("-created_at")

    def perform_create(self, serializer):
        receipt = serializer.save()
        receipt.status = FiscalReceipt.Status.SENT_TO_AGENT
        receipt.save(update_fields=["status", "updated_at"])
        payload = {
            "receipt_pk": receipt.id,
            "device_id": receipt.device_id,
            "idempotency_key": str(receipt.idempotency_key),
            "receipt_payload": receipt.payload,
        }
        DeviceCommand.objects.create(
            clinic_id=receipt.clinic_id,
            device=receipt.device,
            command_type="fiscal_print",
            payload=payload,
            status=DeviceCommand.CommandStatus.PENDING,
        )

    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        receipt = self.get_object()
        if receipt.status == FiscalReceipt.Status.PRINTED:
            return Response({"detail": "Printed receipts cannot be retried."}, status=400)
        receipt.status = FiscalReceipt.Status.SENT_TO_AGENT
        receipt.error_message = ""
        receipt.save(update_fields=["status", "error_message", "updated_at"])
        payload = {
            "receipt_pk": receipt.id,
            "device_id": receipt.device_id,
            "idempotency_key": str(receipt.idempotency_key),
            "receipt_payload": receipt.payload,
        }
        DeviceCommand.objects.create(
            clinic_id=receipt.clinic_id,
            device=receipt.device,
            command_type="fiscal_print",
            payload=payload,
            status=DeviceCommand.CommandStatus.PENDING,
        )
        return Response(self.get_serializer(receipt).data, status=200)
