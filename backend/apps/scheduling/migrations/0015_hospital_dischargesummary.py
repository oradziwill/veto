from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheduling", "0014_hospital_medication_order_and_administration"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HospitalDischargeSummary",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("diagnosis", models.TextField(blank=True)),
                ("hospitalization_course", models.TextField(blank=True)),
                ("procedures", models.TextField(blank=True)),
                ("medications_on_discharge", models.JSONField(blank=True, default=list)),
                ("home_care_instructions", models.TextField(blank=True)),
                ("warning_signs", models.TextField(blank=True)),
                ("follow_up_date", models.DateField(blank=True, null=True)),
                ("finalized_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "clinic",
                    models.ForeignKey(
                        on_delete=models.PROTECT,
                        related_name="hospital_discharge_summaries",
                        to="tenancy.clinic",
                    ),
                ),
                (
                    "generated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="generated_discharge_summaries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "hospital_stay",
                    models.OneToOneField(
                        on_delete=models.CASCADE,
                        related_name="discharge_summary",
                        to="scheduling.hospitalstay",
                    ),
                ),
            ],
            options={"ordering": ["-updated_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="hospitaldischargesummary",
            index=models.Index(
                fields=["clinic", "hospital_stay"],
                name="scheduli_hospita_13ef93_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="hospitaldischargesummary",
            index=models.Index(
                fields=["clinic", "-updated_at"],
                name="scheduli_hospita_9126f4_idx",
            ),
        ),
    ]
