# Generated manually for ConsentDocument

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("patients", "0002_add_ai_summary_cache"),
        ("scheduling", "0017_appointment_booked_via_portal"),
        ("tenancy", "0006_clinic_reminder_sms_enabled"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConsentDocument",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "document_type",
                    models.CharField(
                        choices=[("procedure_consent", "Procedure consent")],
                        default="procedure_consent",
                        max_length=32,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("pending_signature", "Pending signature"), ("signed", "Signed")],
                        db_index=True,
                        default="pending_signature",
                        max_length=32,
                    ),
                ),
                ("template_version", models.CharField(default="1", max_length=16)),
                (
                    "payload_snapshot",
                    models.JSONField(
                        help_text="Frozen fields used to render PDF and content_hash."
                    ),
                ),
                ("content_hash", models.CharField(db_index=True, max_length=64)),
                (
                    "job_id",
                    models.UUIDField(
                        db_index=True, default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                ("final_pdf_s3_key", models.CharField(blank=True, max_length=1024)),
                ("signature_png_s3_key", models.CharField(blank=True, max_length=1024)),
                ("signed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "location_label",
                    models.CharField(
                        blank=True,
                        help_text="Optional workstation label, e.g. reception or exam room.",
                        max_length=120,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "appointment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="consent_documents",
                        to="scheduling.appointment",
                    ),
                ),
                (
                    "clinic",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="consent_documents",
                        to="tenancy.clinic",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_consent_documents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="consent_documents",
                        to="patients.patient",
                    ),
                ),
                (
                    "signed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="signed_consent_documents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="consentdocument",
            index=models.Index(
                fields=["clinic", "appointment", "-created_at"], name="consents_doc_clinic_appt"
            ),
        ),
    ]
