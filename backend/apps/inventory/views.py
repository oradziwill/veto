from __future__ import annotations

from django.db import IntegrityError, models, transaction
from django.db.models import Q
from django.utils.dateparse import parse_date
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
from .services.stock import apply_stock_movement


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
        GET /api/inventory/items/<id>/ledger/?kind=out&limit=50
        Returns item + latest movements for that item.
        """
        user = request.user
        item = self.get_object()

        limit = request.query_params.get("limit")
        try:
            limit_n = int(limit) if limit else 50
        except ValueError:
            limit_n = 50
        limit_n = max(1, min(limit_n, 200))

        kind = request.query_params.get("kind")
        qs = InventoryMovement.objects.filter(
            clinic_id=user.clinic_id, item_id=item.id
        ).select_related("item", "created_by")

        if kind:
            qs = qs.filter(kind=kind)

        qs = qs.order_by("-created_at")[:limit_n]

        return Response(
            {
                "item": InventoryItemReadSerializer(item).data,
                "movements": InventoryMovementReadSerializer(qs, many=True).data,
                "limit": limit_n,
                "filters": {"kind": kind},
            }
        )


class InventoryMovementViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        user = self.request.user
        qs = InventoryMovement.objects.filter(clinic_id=user.clinic_id).select_related(
            "item", "created_by"
        )

        item_id = self.request.query_params.get("item")
        if item_id:
            qs = qs.filter(item_id=item_id)

        kind = self.request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)

        # Optional date range filtering by created_at (YYYY-MM-DD)
        date_from = self.request.query_params.get("date_from")
        if date_from:
            d = parse_date(date_from)
            if d:
                qs = qs.filter(created_at__date__gte=d)

        date_to = self.request.query_params.get("date_to")
        if date_to:
            d = parse_date(date_to)
            if d:
                qs = qs.filter(created_at__date__lte=d)

        return qs.order_by("-created_at")

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return InventoryMovementReadSerializer
        return InventoryMovementWriteSerializer

    def perform_create(self, serializer):
        """
        Use service layer so stock_on_hand is updated atomically and consistently.
        """
        user = self.request.user
        data = serializer.validated_data

        result = apply_stock_movement(
            clinic_id=user.clinic_id,
            item_id=data["item"].id,
            kind=data["kind"],
            quantity=data["quantity"],
            created_by_id=user.id,
            note=data.get("note", ""),
            patient_id=data.get("patient_id"),
            appointment_id=data.get("appointment_id"),
        )

        # Return created movement instance as DRF expects
        movement = InventoryMovement.objects.select_related("item", "created_by").get(
            pk=result.movement_id
        )
        serializer.instance = movement
