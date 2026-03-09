from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0003_country_max_length_100"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="nip",
            field=models.CharField(blank=True, max_length=10),
        ),
    ]
