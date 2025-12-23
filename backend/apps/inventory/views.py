from __future__ import annotations

from django.db import IntegrityError, models, transaction
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsStaffOrVet

from .models import InventoryItem, InventoryMovement
from .serializers import (
    InventoryItemReadSerializer,
    InventoryItemWriteSerializer,
    InventoryMovementReadSerializer,
    InventoryMovementWriteSerializer,
)


class InventoryItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        user = self.request.user
        qs = InventoryItem.objects.filter(clinic_id=user.clinic_id).order_by("name")

        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))

        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)

        low_stock = self.request.query_params.get("low_stock")
        if low_stock in ("1", "true", "True", "yes", "YES"):
            qs = qs.filter(stock_on_hand__lte=models.F("low_stock_threshold"))

        return qs

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
        GET /api/inventory/items/<id>/ledger/
        Returns item snapshot + movements (newest first).

        Optional query params:
          - limit: int (default 50, max 200)
          - kind: in|out|adjust
          - before: ISO datetime (return movements created_at < before)
        """
        user = request.user

        # Ensure item is clinic-scoped
        item = self.get_queryset().filter(pk=pk).first()
        if not item:
            return Response({"detail": "Not found."}, status=404)

        # limit
        limit_raw = request.query_params.get("limit")
        try:
            limit = int(limit_raw) if limit_raw else 50
        except ValueError:
            return Response({"detail": "Invalid limit. Must be an integer."}, status=400)
        limit = max(1, min(limit, 200))

        # filters
        qs = InventoryMovement.objects.filter(clinic_id=user.clinic_id, item_id=item.id)

        kind = request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)

        before = request.query_params.get("before")
        if before:
            dt = parse_datetime(before)
            if dt is None:
                return Response(
                    {"detail": "Invalid before datetime. Use ISO format."},
                    status=400,
                )
            qs = qs.filter(created_at__lt=dt)

        qs = qs.select_related("item").order_by("-created_at")[:limit]

        item_data = InventoryItemReadSerializer(item).data
        movements_data = InventoryMovementReadSerializer(qs, many=True).data

        return Response(
            {
                "item": item_data,
                "movements": movements_data,
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

        return qs.order_by("-created_at")

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return InventoryMovementReadSerializer
        return InventoryMovementWriteSerializer

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(clinic_id=user.clinic_id, created_by=user)
