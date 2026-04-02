from __future__ import annotations

from django.db import models

from apps.inventory.models import InventoryItem
from apps.tenancy.models import Clinic


class ReferenceProduct(models.Model):
    """
    Global regulatory/clinical reference row (not clinic-scoped).
    Payload shape depends on external_source (EMA UPD JSON vs manual rows).
    """

    class ExternalSource(models.TextChoices):
        EMA_UPD = "ema_upd", "EMA Union Product Database"
        MANUAL = "manual", "Manual / clinic-enriched"

    external_source = models.CharField(max_length=16, choices=ExternalSource.choices)
    external_id = models.CharField(
        max_length=256,
        db_index=True,
        help_text="Stable id from source (e.g. EMA product id) or generated for MANUAL.",
    )
    name = models.CharField(max_length=512)
    common_name = models.CharField(max_length=512, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    source_hash = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["external_source", "external_id"],
                name="drug_catalog_refprod_source_extid_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["external_source", "external_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.external_source})"


class SyncRun(models.Model):
    """Log for sync_drug_catalog management command."""

    class Status(models.TextChoices):
        STARTED = "started", "Started"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    class Mode(models.TextChoices):
        FULL = "full", "Full"
        INCREMENTAL = "incremental", "Incremental"

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.STARTED,
    )
    mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.FULL)
    records_processed = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    detail = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"SyncRun({self.started_at}, {self.status})"


class ClinicProductMapping(models.Model):
    """
    Links a clinic inventory line (optional) to a reference product.
    Multiple inventory items may map to the same ReferenceProduct.
    """

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="drug_catalog_mappings",
    )
    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="drug_catalog_mappings",
    )
    reference_product = models.ForeignKey(
        ReferenceProduct,
        on_delete=models.CASCADE,
        related_name="clinic_mappings",
    )
    local_alias = models.CharField(max_length=255, blank=True)
    is_preferred = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "inventory_item"],
                condition=models.Q(inventory_item__isnull=False),
                name="drug_catalog_mapping_clinic_inv_uniq",
            ),
            models.UniqueConstraint(
                fields=["clinic", "reference_product"],
                condition=models.Q(inventory_item__isnull=True),
                name="drug_catalog_mapping_clinic_ref_noinv_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["clinic", "reference_product"]),
        ]

    def __str__(self) -> str:
        return f"ClinicProductMapping(clinic={self.clinic_id}, ref={self.reference_product_id})"
