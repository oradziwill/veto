from __future__ import annotations

from django.db import IntegrityError, models, transaction
from django.db.models import Q
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import HasClinic, IsStaffOrVet
from apps.tenancy.access import accessible_clinic_ids, clinic_id_for_mutation

from .models import InventoryItem, InventoryMovement
from .serializers import (
    InventoryItemReadSerializer,
    InventoryItemWriteSerializer,
    InventoryMovementReadSerializer,
    InventoryMovementWriteSerializer,
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
            qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))

        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)

        low_stock = self.request.query_params.get("low_stock")
        if low_stock in ("1", "true", "True", "yes", "YES"):
            qs = qs.filter(stock_on_hand__lte=models.F("low_stock_threshold"))

        return qs

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
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
            raise serializers.ValidationError(
                {"sku": ["SKU must be unique within the clinic."]}
            ) from err


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
