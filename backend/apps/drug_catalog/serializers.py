from __future__ import annotations

import uuid

from rest_framework import serializers

from .models import ClinicProductMapping, ReferenceProduct


class ReferenceProductListSerializer(serializers.ModelSerializer):
    """Lightweight row for search and autocomplete."""

    class Meta:
        model = ReferenceProduct
        fields = ["id", "external_source", "external_id", "name", "common_name"]


class ReferenceProductDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferenceProduct
        fields = [
            "id",
            "external_source",
            "external_id",
            "name",
            "common_name",
            "payload",
            "last_synced_at",
            "source_hash",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ReferenceProductCreateSerializer(serializers.ModelSerializer):
    """
    Staff-created manual catalog rows only (external_source is always MANUAL).
    Optional external_id must stay unique together with MANUAL source.
    """

    external_id = serializers.CharField(
        max_length=256,
        required=False,
        allow_blank=True,
        help_text="Omit to auto-generate (manual-<uuid>). Must be unique if set.",
    )

    payload = serializers.JSONField(required=False, default=dict)

    class Meta:
        model = ReferenceProduct
        fields = ["name", "common_name", "payload", "external_id"]

    def validate_external_id(self, value):
        if not (value or "").strip():
            return ""
        return value.strip()

    def validate(self, attrs):
        ext = (attrs.get("external_id") or "").strip()
        if (
            ext
            and ReferenceProduct.objects.filter(
                external_source=ReferenceProduct.ExternalSource.MANUAL,
                external_id=ext,
            ).exists()
        ):
            raise serializers.ValidationError(
                {"external_id": ["A manual product with this external_id already exists."]}
            )
        return attrs

    def create(self, validated_data):
        raw_ext = validated_data.pop("external_id", "") or ""
        ext_id = raw_ext.strip() if raw_ext.strip() else f"manual-{uuid.uuid4()}"
        return ReferenceProduct.objects.create(
            external_source=ReferenceProduct.ExternalSource.MANUAL,
            external_id=ext_id,
            **validated_data,
        )


class ClinicProductMappingReadSerializer(serializers.ModelSerializer):
    reference_product = ReferenceProductListSerializer(read_only=True)
    inventory_item_name = serializers.SerializerMethodField()
    inventory_sku = serializers.SerializerMethodField()
    stock_on_hand = serializers.SerializerMethodField()

    class Meta:
        model = ClinicProductMapping
        fields = [
            "id",
            "clinic",
            "inventory_item",
            "inventory_item_name",
            "inventory_sku",
            "stock_on_hand",
            "reference_product",
            "local_alias",
            "is_preferred",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_inventory_item_name(self, obj):
        if not obj.inventory_item_id:
            return None
        return obj.inventory_item.name

    def get_inventory_sku(self, obj):
        if not obj.inventory_item_id:
            return None
        return obj.inventory_item.sku

    def get_stock_on_hand(self, obj):
        if not obj.inventory_item_id:
            return None
        return obj.inventory_item.stock_on_hand


class ClinicProductMappingWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicProductMapping
        fields = [
            "inventory_item",
            "reference_product",
            "local_alias",
            "is_preferred",
            "notes",
        ]

    def validate_inventory_item(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        clinic_id = getattr(request.user, "clinic_id", None) if request else None
        if clinic_id and value.clinic_id != clinic_id:
            raise serializers.ValidationError("Inventory item must belong to your clinic.")
        return value

    def validate_reference_product(self, value):
        if value is None:
            raise serializers.ValidationError("reference_product is required.")
        return value
