# Generated manually

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("drug_catalog", "0001_initial"),
        ("medical", "0012_procedure_supply_templates"),
    ]

    operations = [
        migrations.AddField(
            model_name="prescription",
            name="reference_product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="prescriptions",
                to="drug_catalog.referenceproduct",
            ),
        ),
        migrations.AddIndex(
            model_name="prescription",
            index=models.Index(fields=["reference_product"], name="med_prescription_refprod_idx"),
        ),
    ]
