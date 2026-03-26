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
            name="AuditLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("request_id", models.CharField(blank=True, max_length=64)),
                ("action", models.CharField(max_length=64)),
                ("entity_type", models.CharField(max_length=64)),
                ("entity_id", models.CharField(max_length=64)),
                ("before", models.JSONField(blank=True, default=dict)),
                ("after", models.JSONField(blank=True, default=dict)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "clinic",
                    models.ForeignKey(
                        on_delete=models.PROTECT,
                        related_name="audit_logs",
                        to="tenancy.clinic",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(
                fields=["clinic", "created_at"], name="audit_audlo_clinic__5fce9d_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["clinic", "action"], name="audit_audlo_clinic__ad06da_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(
                fields=["clinic", "entity_type", "entity_id"],
                name="audit_audlo_clinic__406f18_idx",
            ),
        ),
    ]
