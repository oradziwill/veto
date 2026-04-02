# Generated manually for drug_catalog app

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("inventory", "0005_add_is_active_back_to_inventoryitem"),
        ("tenancy", "0006_clinic_reminder_sms_enabled"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReferenceProduct",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "external_source",
                    models.CharField(
                        choices=[
                            ("ema_upd", "EMA Union Product Database"),
                            ("manual", "Manual / clinic-enriched"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "external_id",
                    models.CharField(
                        db_index=True,
                        help_text="Stable id from source (e.g. EMA product id) or generated for MANUAL.",
                        max_length=256,
                    ),
                ),
                ("name", models.CharField(max_length=512)),
                ("common_name", models.CharField(blank=True, default="", max_length=512)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("source_hash", models.CharField(blank=True, default="", max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name", "id"],
            },
        ),
        migrations.CreateModel(
            name="SyncRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("started", "Started"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                        ],
                        default="started",
                        max_length=16,
                    ),
                ),
                (
                    "mode",
                    models.CharField(
                        choices=[("full", "Full"), ("incremental", "Incremental")],
                        default="full",
                        max_length=16,
                    ),
                ),
                ("records_processed", models.PositiveIntegerField(default=0)),
                ("error_message", models.TextField(blank=True)),
                ("detail", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["-started_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="referenceproduct",
            constraint=models.UniqueConstraint(
                fields=("external_source", "external_id"),
                name="drug_catalog_refprod_source_extid_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="referenceproduct",
            index=models.Index(fields=["name"], name="drug_catalog_name_0c0c9c_idx"),
        ),
        migrations.AddIndex(
            model_name="referenceproduct",
            index=models.Index(
                fields=["external_source", "external_id"],
                name="drug_catalog_externa_7f3b2c_idx",
            ),
        ),
        migrations.CreateModel(
            name="ClinicProductMapping",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("local_alias", models.CharField(blank=True, max_length=255)),
                ("is_preferred", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "clinic",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="drug_catalog_mappings",
                        to="tenancy.clinic",
                    ),
                ),
                (
                    "inventory_item",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="drug_catalog_mappings",
                        to="inventory.inventoryitem",
                    ),
                ),
                (
                    "reference_product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="clinic_mappings",
                        to="drug_catalog.referenceproduct",
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="clinicproductmapping",
            constraint=models.UniqueConstraint(
                condition=Q(inventory_item__isnull=False),
                fields=("clinic", "inventory_item"),
                name="drug_catalog_mapping_clinic_inv_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="clinicproductmapping",
            constraint=models.UniqueConstraint(
                condition=Q(inventory_item__isnull=True),
                fields=("clinic", "reference_product"),
                name="drug_catalog_mapping_clinic_ref_noinv_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="clinicproductmapping",
            index=models.Index(
                fields=["clinic", "reference_product"],
                name="drug_catalog_clinic__f4e1a2_idx",
            ),
        ),
    ]
