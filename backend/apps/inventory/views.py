from __future__ import annotations

from django.db import IntegrityError, models, transaction
from django.db.models import Q
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsStaffOrVet
from apps.tenancy.access import accessible_clinic_ids, clinic_id_for_mutation

from .models import InventoryItem, InventoryMovement
from .serializers import (
    InventoryItemReadSerializer,
    InventoryItemWriteSerializer,
    InventoryMovementReadSerializer,
    InventoryMovementWriteSerializer,
    normalize_inventory_barcode,
)
from .services.stock import apply_movement


class InventoryItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        ids = accessible_clinic_ids(self.request.user)
        if not ids:
            return InventoryItem.objects.none()
        qs = InventoryItem.objects.filter(clinic_id__in=ids).order_by("name")

        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q))

        raw_barcode = self.request.query_params.get("barcode")
        if raw_barcode is not None and str(raw_barcode).strip() != "":
            try:
                bc = normalize_inventory_barcode(raw_barcode)
            except serializers.ValidationError as err:
                raise serializers.ValidationError({"barcode": err.detail}) from err
            if bc:
                qs = qs.filter(barcode=bc)

        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)

        low_stock = self.request.query_params.get("low_stock")
        if low_stock in ("1", "true", "True", "yes", "YES"):
            qs = qs.filter(stock_on_hand__lte=models.F("low_stock_threshold"))

        return qs

    def get_serializer_class(self):
        if self.action in ("list", "retrieve", "resolve_barcode"):
            return InventoryItemReadSerializer
        return InventoryItemWriteSerializer

    def perform_create(self, serializer):
        """
        Creating an InventoryItem should NOT call apply_movement().
        Stock changes happen via InventoryMovement only.
        """
        user = self.request.user
        cid = clinic_id_for_mutation(user, request=self.request, instance_clinic_id=None)
        try:
            with transaction.atomic():
                serializer.save(clinic_id=cid, created_by=user)
        except IntegrityError as err:
            err_s = str(err).lower()
            if "barcode" in err_s or "uniq_inventory_barcode" in err_s:
                raise serializers.ValidationError(
                    {"barcode": ["Barcode must be unique within the clinic."]}
                ) from err
            raise serializers.ValidationError(
                {"sku": ["SKU must be unique within the clinic."]}
            ) from err

    @action(detail=False, methods=["get"], url_path="resolve_barcode")
    def resolve_barcode(self, request):
        """
        Resolve a single inventory line by package barcode (exact match, clinic-scoped).
        Used for wholesale intake: scan → item id → POST inventory movement (kind=in).
        """
        raw = request.query_params.get("code", "")
        if not str(raw).strip():
            return Response(
                {"detail": "Query parameter 'code' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            bc = normalize_inventory_barcode(raw)
        except serializers.ValidationError as err:
            return Response({"barcode": err.detail}, status=status.HTTP_400_BAD_REQUEST)

        if not bc:
            return Response(
                {"detail": "Query parameter 'code' cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids = accessible_clinic_ids(request.user)
        if not ids:
            return Response(status=status.HTTP_404_NOT_FOUND)

        qs = InventoryItem.objects.filter(clinic_id__in=ids, barcode=bc).order_by("name")
        n = qs.count()
        if n == 0:
            return Response(
                {"detail": "No inventory item matches this barcode."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if n > 1:
            return Response(
                {
                    "detail": (
                        "Multiple inventory items match this barcode; "
                        "resolve the conflict in data or narrow clinic scope."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        item = qs.first()
        ser = InventoryItemReadSerializer(item, context={"request": request})
        return Response(ser.data, status=status.HTTP_200_OK)


class InventoryMovementViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        ids = accessible_clinic_ids(self.request.user)
        if not ids:
            return InventoryMovement.objects.none()
        qs = InventoryMovement.objects.filter(clinic_id__in=ids).select_related("item")

        item_id = self.request.query_params.get("item")
        if item_id:
            qs = qs.filter(item_id=item_id)

        return qs.order_by("-created_at")

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return InventoryMovementReadSerializer
        return InventoryMovementWriteSerializer

    def perform_create(self, serializer):
        user = self.request.user
        item = serializer.validated_data["item"]
        try:
            with transaction.atomic():
                movement = serializer.save(clinic_id=item.clinic_id, created_by=user)
                apply_movement(movement)
        except Exception as err:
            raise serializers.ValidationError({"detail": str(err)}) from err
