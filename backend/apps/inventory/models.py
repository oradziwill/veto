from django.db import models

from apps.tenancy.models import Clinic


class InventoryItem(models.Model):
    class Category(models.TextChoices):
        MEDICATION = "medication", "Medication"
        SUPPLIES = "supplies", "Supplies"
        EQUIPMENT = "equipment", "Equipment"
        OTHER = "other", "Other"

    clinic = models.ForeignKey(Clinic, on_delete=models.PROTECT, related_name="inventory_items")

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    description = models.TextField(blank=True)

    stock_quantity = models.IntegerField(default=0)
    unit = models.CharField(max_length=50, default="units")
    min_stock_level = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["clinic", "category"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.stock_quantity} {self.unit})"

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.min_stock_level

    @property
    def is_out_of_stock(self):
        return self.stock_quantity == 0
