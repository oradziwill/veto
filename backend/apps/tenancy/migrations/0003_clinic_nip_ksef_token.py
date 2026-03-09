from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0002_clinicholiday"),
    ]

    operations = [
        migrations.AddField(
            model_name="clinic",
            name="nip",
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name="clinic",
            name="ksef_token",
            field=models.CharField(blank=True, max_length=512),
        ),
    ]
