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
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("SKU is required.")
        return value

    def validate(self, attrs):
        """
        Enforce uniqueness of (clinic, sku) at the serializer level so we return 400,
        not a 500 IntegrityError.
        """
        request = self.context.get("request")
        clinic_id = getattr(getattr(request, "user", None), "clinic_id", None)
        if not clinic_id:
            # HasClinic permission should guarantee this, but keep it safe.
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
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = InventoryMovement
        fields = [
            "id",
            "clinic",
            "item",
            "item_name",
            "item_sku",
            "kind",
            "quantity",
            "note",
            "patient_id",
            "appointment_id",
            "created_by",
            "created_by_name",
            "created_at",
        ]
        read_only_fields = ["id", "clinic", "created_by", "created_at"]


class InventoryMovementWriteSerializer(serializers.ModelSerializer):
    """
    This serializer validates request payload only.
    Stock mutation is done in the view inside a DB transaction.
    """

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

    def validate_quantity(self, value: int) -> int:
        if value is None or value <= 0:
            raise serializers.ValidationError("quantity must be > 0")
        return value

    def validate(self, attrs):
        """
        Validate:
        - item must belong to the user's clinic
        - OUT must not exceed current stock (best-effort; final enforcement in transaction)
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        clinic_id = getattr(user, "clinic_id", None)

        item: InventoryItem = attrs.get("item")
        if clinic_id and item and item.clinic_id != clinic_id:
            raise serializers.ValidationError({"item": "Item must belong to your clinic."})

        kind = attrs.get("kind")
        qty = attrs.get("quantity") or 0

        # Best-effort: prevent obvious negatives early.
        # Final check is enforced in the locked transaction in the view.
        if kind == InventoryMovement.Kind.OUT and item:
            if qty > item.stock_on_hand:
                raise serializers.ValidationError(
                    {"quantity": f"Not enough stock. On hand: {item.stock_on_hand}."}
                )

        return attrs
