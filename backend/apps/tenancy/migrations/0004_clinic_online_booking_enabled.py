from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0003_clinic_nip_ksef_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="clinic",
            name="online_booking_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Allow pet owners to request appointments via the public booking portal.",
            ),
        ),
    ]
