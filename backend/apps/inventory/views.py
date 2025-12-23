from __future__ import annotations

from django.db import IntegrityError, transaction
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsStaffOrVet

from .models import InventoryMovement
from .serializers import (
    InventoryItemReadSerializer,
    InventoryItemWriteSerializer,
    InventoryMovementReadSerializer,
    InventoryMovementWriteSerializer,
)
from .services.stock import StockError, apply_inventory_movement


class InventoryItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        user = self.request.user
        qs = InventoryMovement.objects.filter(clinic_id=user.clinic_id).select_related("item")

        item_id = self.request.query_params.get("item")
        if item_id:
            qs = qs.filter(item_id=item_id)

        kind = self.request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)

        return qs.order_by("-created_at")

    def get_serializer_class(self):
        if self.action in ("list", "retrieve", "ledger"):
            return InventoryItemReadSerializer
        return InventoryItemWriteSerializer

    def perform_create(self, serializer):
        user = self.request.user
        try:
            with transaction.atomic():
                serializer.save(clinic_id=user.clinic_id, created_by=user)
        except IntegrityError as err:
            raise serializers.ValidationError(
                {"sku": ["SKU must be unique within the clinic."]}
            ) from err

    @action(detail=True, methods=["get"], url_path="ledger")
    def ledger(self, request, pk=None):
        """
        Return item + recent movements.
        Query params:
          - limit (default 50, max 200)
          - kind (optional)
          - before (optional ISO datetime, filter created_at__lt)
        """
        user = request.user
        item = self.get_queryset().filter(pk=pk).first()
        if not item:
            return Response({"detail": "Not found."}, status=404)

        limit_raw = request.query_params.get("limit") or "50"
        try:
            limit = max(1, min(int(limit_raw), 200))
        except ValueError:
            limit = 50

        kind = request.query_params.get("kind")
        before = request.query_params.get("before")

        mqs = InventoryMovement.objects.filter(
            clinic_id=user.clinic_id, item_id=item.id
        ).select_related("item")

        if kind:
            mqs = mqs.filter(kind=kind)

        if before:
            mqs = mqs.filter(created_at__lt=before)

        mqs = mqs.order_by("-created_at")[:limit]

        return Response(
            {
                "item": InventoryItemReadSerializer(item).data,
                "movements": InventoryMovementReadSerializer(mqs, many=True).data,
                "limit": limit,
                "filters": {"kind": kind, "before": before},
            }
        )


class InventoryMovementViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        user = self.request.user
        qs = InventoryMovement.objects.filter(clinic_id=user.clinic_id).select_related("item")

        item_id = self.request.query_params.get("item")
        if item_id:
            qs = qs.filter(item_id=item_id)

        kind = self.request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)

        date_from = self.request.query_params.get("date_from")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        date_to = self.request.query_params.get("date_to")
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        return qs.order_by("-created_at")

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return InventoryMovementReadSerializer
        return InventoryMovementWriteSerializer

    def perform_create(self, serializer):
        user = self.request.user

        item = serializer.validated_data["item"]
        kind = serializer.validated_data["kind"]
        qty = serializer.validated_data["quantity"]

        # Atomic: lock item row, apply stock change, then create movement.
        try:
            with transaction.atomic():
                apply_inventory_movement(
                    clinic_id=user.clinic_id,
                    item_id=item.id,
                    kind=kind,
                    quantity=qty,
                )
                serializer.save(clinic_id=user.clinic_id, created_by=user)
        except StockError as err:
            raise serializers.ValidationError({"detail": str(err)}) from err
