import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("clients", "0004_client_nip"),
        ("tenancy", "0004_clinic_online_booking_enabled"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalLoginChallenge",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("code_hash", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portal_login_challenges",
                        to="clients.client",
                    ),
                ),
                (
                    "clinic",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portal_login_challenges",
                        to="tenancy.clinic",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["clinic", "client", "-created_at"],
                        name="portal_plc_clinic_crt_idx",
                    )
                ],
            },
        ),
    ]
