import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0003_ksef_fields"),
        ("scheduling", "0015_hospital_dischargesummary"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="portal_deposit_invoice",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="portal_deposit_appointments",
                to="billing.invoice",
            ),
        ),
    ]
