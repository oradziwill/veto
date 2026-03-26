from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("tenancy", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ReportExportJob",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "report_type",
                    models.CharField(
                        choices=[
                            ("revenue_summary", "Revenue Summary"),
                            ("reminder_analytics", "Reminder Analytics"),
                            ("cancellation_analytics", "Cancellation Analytics"),
                        ],
                        max_length=64,
                    ),
                ),
                ("params", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("file_name", models.CharField(blank=True, max_length=255)),
                ("file_content", models.TextField(blank=True)),
                ("content_type", models.CharField(default="text/csv", max_length=64)),
                ("error", models.TextField(blank=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "clinic",
                    models.ForeignKey(
                        on_delete=models.PROTECT,
                        related_name="report_export_jobs",
                        to="tenancy.clinic",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="requested_report_exports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="reportexportjob",
            index=models.Index(
                fields=["clinic", "status", "created_at"],
                name="reports_rep_clinic__676dc9_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="reportexportjob",
            index=models.Index(
                fields=["clinic", "report_type", "created_at"],
                name="reports_rep_clinic__c811cf_idx",
            ),
        ),
    ]
