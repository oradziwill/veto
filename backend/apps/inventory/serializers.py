from __future__ import annotations

import re

from rest_framework import serializers

from apps.scheduling.models import Appointment
from apps.tenancy.access import accessible_clinic_ids, clinic_id_for_mutation

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
        Normalize SKU so user input like "bandage roll" becomes "BANDAGE_ROLL".
        """
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("SKU is required.")

        value = value.upper()
        value = re.sub(r"[^A-Z0-9]+", "_", value)  # spaces/dashes/etc -> underscore
        value = re.sub(r"_+", "_", value)  # collapse multiple underscores
        value = value.strip("_")
        return value

    def validate(self, attrs):
        """
        Enforce uniqueness of (clinic, sku) at the serializer level so we return 400,
        not a 500 IntegrityError.
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user:
            return attrs

        if self.instance:
            effective_clinic_id = self.instance.clinic_id
            if effective_clinic_id not in set(accessible_clinic_ids(user)):
                raise serializers.ValidationError("Clinic not accessible.")
        else:
            effective_clinic_id = clinic_id_for_mutation(
                user, request=request, instance_clinic_id=None
            )

        sku = attrs.get("sku") or getattr(self.instance, "sku", None)
        if sku:
            qs = InventoryItem.objects.filter(clinic_id=effective_clinic_id, sku=sku)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"sku": ["SKU must be unique within the clinic."]}
                )

        return attrs


class InventoryMovementReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryMovement
        fields = "__all__"


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
        request = self.context.get("request")
        user = getattr(request, "user", None)
        accessible = set(accessible_clinic_ids(user)) if user else set()

        qty = attrs.get("quantity")
        if qty is not None and qty <= 0:
            raise serializers.ValidationError({"quantity": "quantity must be > 0"})

        item = attrs.get("item")
        if item and item.clinic_id not in accessible:
            raise serializers.ValidationError(
                {"item": "Inventory item must belong to a clinic you can access."}
            )

        effective_clinic_id = item.clinic_id if item else None

        appointment_id = attrs.get("appointment_id")
        if appointment_id and effective_clinic_id:
            try:
                appt = Appointment.objects.get(pk=appointment_id, clinic_id=effective_clinic_id)
            except Appointment.DoesNotExist as err:
                raise serializers.ValidationError(
                    {"appointment_id": "Appointment must belong to your clinic."}
                ) from err

            patient_id = attrs.get("patient_id")
            if patient_id and appt.patient_id and patient_id != appt.patient_id:
                raise serializers.ValidationError(
                    {"patient_id": "patient_id must match appointment.patient_id."}
                )

        return attrs
