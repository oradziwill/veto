# Generated manually for inventory barcode (EAN/GTIN) support.

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0005_add_is_active_back_to_inventoryitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventoryitem",
            name="barcode",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddConstraint(
            model_name="inventoryitem",
            constraint=models.UniqueConstraint(
                fields=("clinic", "barcode"),
                condition=~Q(barcode=""),
                name="uniq_inventory_barcode_per_clinic_when_set",
            ),
        ),
        migrations.AddIndex(
            model_name="inventoryitem",
            index=models.Index(fields=["clinic", "barcode"], name="inventory_inv_clinic__idx"),
        ),
    ]
