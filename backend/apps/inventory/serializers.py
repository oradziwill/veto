from __future__ import annotations

from rest_framework import serializers

from .models import InventoryItem, InventoryMovement


class InventoryItemReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryItem
        fields = "__all__"


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
        # Canonical format: trim, upper, spaces -> underscores
        value = (value or "").strip().upper().replace(" ", "_")
        if not value:
            raise serializers.ValidationError("SKU is required.")
        return value

    def validate(self, attrs):
        """
        Enforce uniqueness of (clinic, sku) at the serializer level
        so we return 400 instead of a DB 500.
        """
        request = self.context.get("request")
        clinic_id = getattr(getattr(request, "user", None), "clinic_id", None)
        if not clinic_id:
            # HasClinic should guarantee clinic_id, but keep safe.
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

    def get_created_by_name(self, obj) -> str:
        user = getattr(obj, "created_by", None)
        if not user:
            return ""
        return getattr(user, "username", "") or getattr(user, "email", "") or str(user)


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
        if qty is None or qty <= 0:
            raise serializers.ValidationError({"quantity": "quantity must be > 0"})

        kind = attrs.get("kind")
        if kind not in InventoryMovement.Kind.values:
            raise serializers.ValidationError({"kind": "Invalid kind."})

        # We treat ADJUST as absolute: quantity is the new stock_on_hand (>= 0).
        if kind == InventoryMovement.Kind.ADJUST and qty < 0:
            raise serializers.ValidationError({"quantity": "adjust quantity must be >= 0"})

        return attrs
