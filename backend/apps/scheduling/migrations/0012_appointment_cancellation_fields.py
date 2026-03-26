from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "scheduling",
            "0011_rename_scheduling_v_clinic__7d9698_idx_scheduling__clinic__49235b_idx_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="cancellation_reason",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="appointment",
            name="cancelled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="appointment",
            name="cancelled_by",
            field=models.CharField(
                blank=True,
                choices=[("client", "Client"), ("clinic", "Clinic")],
                max_length=20,
            ),
        ),
    ]
