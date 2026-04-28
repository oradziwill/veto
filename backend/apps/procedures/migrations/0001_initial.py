from __future__ import annotations

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("patients", "0002_add_ai_summary_cache"),
        ("scheduling", "0019_visittrancriptionjob_appointment_nullable"),
        ("accounts", "0003_user_network_admin"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClinicalProcedure",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("slug", models.SlugField(max_length=100, unique=True)),
                ("name", models.CharField(max_length=200)),
                ("name_en", models.CharField(blank=True, max_length=200)),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("dermatology", "Dermatologia"),
                            ("gastroenterology", "Gastroenterologia"),
                            ("cardiology", "Kardiologia"),
                            ("neurology", "Neurologia"),
                            ("internal_medicine", "Interna"),
                            ("preventive_care", "Medycyna zapobiegawcza"),
                            ("emergency", "Nagłe przypadki"),
                            ("urology", "Urologia"),
                            ("orthopedics", "Ortopedia"),
                            ("oncology", "Onkologia"),
                        ],
                        max_length=50,
                    ),
                ),
                ("species", models.JSONField(default=list)),
                ("entry_node_id", models.CharField(max_length=100)),
                ("nodes", models.JSONField()),
                ("tags", models.JSONField(blank=True, default=list)),
                ("source", models.TextField(blank=True)),
                ("last_reviewed", models.DateField(blank=True, null=True)),
                ("reviewed_by", models.CharField(blank=True, max_length=200)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="VisitProcedureSession",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "appointment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="procedure_sessions",
                        to="scheduling.appointment",
                    ),
                ),
                (
                    "procedure",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sessions",
                        to="procedures.clinicalprocedure",
                    ),
                ),
                (
                    "doctor",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="procedure_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="procedure_sessions",
                        to="patients.patient",
                    ),
                ),
                ("path", models.JSONField(default=list)),
                ("collected_data", models.JSONField(default=dict)),
                ("result", models.JSONField(default=dict)),
                ("result_node_id", models.CharField(blank=True, max_length=100)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
