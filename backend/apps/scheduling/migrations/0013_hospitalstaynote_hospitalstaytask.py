from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheduling", "0012_appointment_cancellation_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HospitalStayNote",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("note_type", models.CharField(blank=True, default="round", max_length=40)),
                ("note", models.TextField()),
                ("vitals", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "clinic",
                    models.ForeignKey(
                        on_delete=models.PROTECT,
                        related_name="hospital_stay_notes",
                        to="tenancy.clinic",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="hospital_stay_notes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "hospital_stay",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="notes",
                        to="scheduling.hospitalstay",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="HospitalStayTask",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                (
                    "priority",
                    models.CharField(
                        choices=[("low", "Low"), ("normal", "Normal"), ("high", "High")],
                        default="normal",
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("in_progress", "In progress"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "clinic",
                    models.ForeignKey(
                        on_delete=models.PROTECT,
                        related_name="hospital_stay_tasks",
                        to="tenancy.clinic",
                    ),
                ),
                (
                    "completed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="completed_hospital_stay_tasks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="created_hospital_stay_tasks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "hospital_stay",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="tasks",
                        to="scheduling.hospitalstay",
                    ),
                ),
            ],
            options={"ordering": ["status", "due_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="hospitalstaynote",
            index=models.Index(
                fields=["clinic", "hospital_stay", "-created_at"],
                name="scheduli_hospita_1a2f2c_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="hospitalstaytask",
            index=models.Index(
                fields=["clinic", "hospital_stay", "status"],
                name="scheduli_hospita_0c0f9a_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="hospitalstaytask",
            index=models.Index(
                fields=["clinic", "due_at"],
                name="scheduli_hospita_8c7856_idx",
            ),
        ),
    ]
