from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheduling", "0013_hospitalstaynote_hospitalstaytask"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HospitalMedicationOrder",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("medication_name", models.CharField(max_length=255)),
                ("dose", models.DecimalField(decimal_places=2, max_digits=8)),
                ("dose_unit", models.CharField(default="mg", max_length=32)),
                ("route", models.CharField(blank=True, default="", max_length=32)),
                ("frequency_hours", models.PositiveSmallIntegerField(default=8)),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("instructions", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "clinic",
                    models.ForeignKey(
                        on_delete=models.PROTECT,
                        related_name="hospital_medication_orders",
                        to="tenancy.clinic",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="created_hospital_medication_orders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "hospital_stay",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="medication_orders",
                        to="scheduling.hospitalstay",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="HospitalMedicationAdministration",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("scheduled_for", models.DateTimeField(blank=True, null=True)),
                ("administered_at", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("given", "Given"),
                            ("skipped", "Skipped"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "administered_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="hospital_medication_administrations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "clinic",
                    models.ForeignKey(
                        on_delete=models.PROTECT,
                        related_name="hospital_medication_administrations",
                        to="tenancy.clinic",
                    ),
                ),
                (
                    "medication_order",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="administrations",
                        to="scheduling.hospitalmedicationorder",
                    ),
                ),
            ],
            options={"ordering": ["-scheduled_for", "-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="hospitalmedicationorder",
            index=models.Index(
                fields=["clinic", "hospital_stay", "is_active"],
                name="scheduli_hospita_7740cc_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="hospitalmedicationadministration",
            index=models.Index(
                fields=["clinic", "status", "scheduled_for"],
                name="scheduli_hospita_7d2ec2_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="hospitalmedicationadministration",
            index=models.Index(
                fields=["clinic", "medication_order"],
                name="scheduli_hospita_91e80a_idx",
            ),
        ),
    ]
