from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0007_clinic_network"),
    ]

    operations = [
        migrations.AddField(
            model_name="clinic",
            name="feature_ai_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Patient AI summary and scheduling assistant (capacity / optimization).",
            ),
        ),
        migrations.AddField(
            model_name="clinic",
            name="feature_ksef_enabled",
            field=models.BooleanField(
                default=True,
                help_text="KSeF invoice submission and XML preview in staff API.",
            ),
        ),
        migrations.AddField(
            model_name="clinic",
            name="feature_portal_deposit_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Portal booking deposit flow; when off, bookings confirm without a deposit even if amount > 0.",
            ),
        ),
    ]
