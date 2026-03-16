from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reminders", "0004_reminderproviderconfig"),
    ]

    operations = [
        migrations.AddField(
            model_name="reminder",
            name="experiment_key",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="reminder",
            name="experiment_variant",
            field=models.CharField(default="control", max_length=32),
        ),
        migrations.AddIndex(
            model_name="reminder",
            index=models.Index(
                fields=["clinic", "experiment_key", "experiment_variant"],
                name="reminders_r_clinic__731820_idx",
            ),
        ),
    ]
