from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reminders", "0005_reminder_experiment_key_reminder_experiment_variant_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reminderevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("enqueued", "Enqueued"),
                    ("deferred", "Deferred"),
                    ("sent", "Sent"),
                    ("failed", "Failed"),
                    ("cancelled", "Cancelled"),
                    ("webhook_update", "Webhook update"),
                    ("reply_received", "Reply received"),
                ],
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="ReminderInboundReply",
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
                    "provider",
                    models.CharField(
                        choices=[
                            ("internal", "Internal"),
                            ("sendgrid", "SendGrid"),
                            ("twilio", "Twilio"),
                        ],
                        max_length=20,
                    ),
                ),
                ("provider_reply_id", models.CharField(max_length=255)),
                ("provider_message_id", models.CharField(blank=True, max_length=255)),
                ("raw_text", models.TextField(blank=True)),
                (
                    "normalized_intent",
                    models.CharField(
                        choices=[
                            ("confirm", "Confirm"),
                            ("cancel", "Cancel"),
                            ("reschedule", "Reschedule"),
                            ("unknown", "Unknown"),
                        ],
                        default="unknown",
                        max_length=20,
                    ),
                ),
                (
                    "action_status",
                    models.CharField(
                        choices=[
                            ("applied", "Applied"),
                            ("needs_review", "Needs review"),
                            ("ignored", "Ignored"),
                        ],
                        default="needs_review",
                        max_length=20,
                    ),
                ),
                ("action_note", models.CharField(blank=True, max_length=255)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "clinic",
                    models.ForeignKey(
                        on_delete=models.deletion.PROTECT,
                        related_name="reminder_inbound_replies",
                        to="tenancy.clinic",
                    ),
                ),
                (
                    "reminder",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="inbound_replies",
                        to="reminders.reminder",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="reminderinboundreply",
            index=models.Index(
                fields=["clinic", "action_status", "created_at"],
                name="reminders_r_clinic__7296cd_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="reminderinboundreply",
            index=models.Index(
                fields=["reminder", "created_at"], name="reminders_r_reminde_4c9d88_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="reminderinboundreply",
            constraint=models.UniqueConstraint(
                fields=("provider", "provider_reply_id"),
                name="reminders_reply_provider_reply_id_uniq",
            ),
        ),
    ]
