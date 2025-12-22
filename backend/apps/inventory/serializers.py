from rest_framework import serializers
from .models import InventoryItem


class InventoryItemSerializer(serializers.ModelSerializer):
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = InventoryItem
        fields = [
            "id",
            "clinic",
            "name",
            "category",
            "description",
            "stock_quantity",
            "unit",
            "min_stock_level",
            "is_low_stock",
            "is_out_of_stock",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["clinic", "created_at", "updated_at"]

