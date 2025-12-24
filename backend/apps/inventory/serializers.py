from __future__ import annotations

import re

from rest_framework import serializers

from .models import InventoryItem, InventoryMovement


class InventoryItemReadSerializer(serializers.ModelSerializer):
    is_low_stock = serializers.SerializerMethodField()

    class Meta:
        model = InventoryItem
        fields = "__all__"

    def get_is_low_stock(self, obj: InventoryItem) -> bool:
        try:
            return obj.stock_on_hand <= obj.low_stock_threshold
        except TypeError:
            return False


class InventoryItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryItem
        fields = [
            "name",
            "sku",
            "category",
            "unit",
            "stock_on_hand",
            "low_stock_threshold",
        ]

    def validate_sku(self, value: str) -> str:
        """
        Normalize SKU so we avoid case/space duplicates:
        - strip
        - uppercase
        - replace whitespace with underscore
        - collapse multiple underscores
        - allow A-Z, 0-9, underscore, dash
        """
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("SKU is required.")

        value = value.upper()
        value = re.sub(r"\s+", "_", value)
        value = re.sub(r"_+", "_", value)

        if not re.fullmatch(r"[A-Z0-9_-]+", value):
            raise serializers.ValidationError(
                "SKU may contain only letters, numbers, underscore, and dash."
            )

        return value

    def validate(self, attrs):
        """
        Enforce uniqueness of (clinic, sku) at serializer level -> clean 400, not 500.
        """
        request = self.context.get("request")
        clinic_id = getattr(getattr(request, "user", None), "clinic_id", None)
        if not clinic_id:
            return attrs

        sku = attrs.get("sku") or getattr(self.instance, "sku", None)
        if sku:
            qs = InventoryItem.objects.filter(clinic_id=clinic_id, sku=sku)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"sku": ["SKU must be unique within the clinic."]}
                )

        return attrs


class InventoryMovementReadSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryMovement
        fields = "__all__"

    def get_created_by_name(self, obj: InventoryMovement) -> str:
        user = getattr(obj, "created_by", None)
        if not user:
            return ""
        return (
            getattr(user, "username", "")
            or f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
        )


class InventoryMovementWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryMovement
        fields = [
            "item",
            "kind",
            "quantity",
            "note",
            "patient_id",
            "appointment_id",
        ]

    def validate(self, attrs):
        qty = attrs.get("quantity")
        if qty is not None and qty <= 0:
            raise serializers.ValidationError({"quantity": "quantity must be > 0"})
        return attrs
