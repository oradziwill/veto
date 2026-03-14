from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("billing", "0003_ksef_fields"),
        ("medical", "0007_prescription_drug_fields"),
        ("patients", "0002_add_ai_summary_cache"),
        ("scheduling", "0008_add_shift_hours_to_clinic_working_hours"),
        ("tenancy", "0003_clinic_nip_ksef_token"),
    ]

    operations = [
        migrations.CreateModel(
            name="Reminder",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "reminder_type",
                    models.CharField(
                        choices=[
                            ("appointment", "Appointment"),
                            ("vaccination", "Vaccination"),
                            ("invoice", "Invoice"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "channel",
                    models.CharField(
                        choices=[("email", "Email"), ("sms", "SMS")], default="email", max_length=10
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("sent", "Sent"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="queued",
                        max_length=12,
                    ),
                ),
                ("recipient", models.CharField(blank=True, max_length=255)),
                ("subject", models.CharField(blank=True, max_length=255)),
                ("body", models.TextField(blank=True)),
                ("scheduled_for", models.DateTimeField(default=django.utils.timezone.now)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("max_attempts", models.PositiveIntegerField(default=3)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "appointment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reminders",
                        to="scheduling.appointment",
                    ),
                ),
                (
                    "clinic",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reminders",
                        to="tenancy.clinic",
                    ),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reminders",
                        to="billing.invoice",
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reminders",
                        to="patients.patient",
                    ),
                ),
                (
                    "vaccination",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reminders",
                        to="medical.vaccination",
                    ),
                ),
            ],
            options={
                "ordering": ["scheduled_for", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="reminder",
            index=models.Index(
                fields=["clinic", "status", "scheduled_for"], name="reminders_r_clinic__87ca59_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="reminder",
            index=models.Index(
                fields=["clinic", "reminder_type", "status"], name="reminders_r_clinic__1d606e_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="reminder",
            index=models.Index(
                fields=["clinic", "channel", "status"], name="reminders_r_clinic__898889_idx"
            ),
        ),
    ]
