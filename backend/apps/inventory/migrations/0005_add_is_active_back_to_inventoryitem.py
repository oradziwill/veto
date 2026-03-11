# Restore is_active so INSERTs work whether 0004 was applied or not.
# If 0004 already ran (column dropped), this adds it back with default=True.

from django.db import migrations, models
from django.db.models import Count


def deduplicate_inventoryitem_sku(apps, schema_editor):
    """Ensure (clinic_id, sku) is unique before any table rebuild (e.g. AddField on SQLite)."""
    InventoryItem = apps.get_model("inventory", "InventoryItem")
    dupes = (
        InventoryItem.objects.values("clinic_id", "sku")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
    )
    for row in dupes:
        clinic_id, sku = row["clinic_id"], row["sku"]
        items = list(
            InventoryItem.objects.filter(clinic_id=clinic_id, sku=sku).order_by("id")
        )
        base_sku = (sku or "").strip() or "mig"
        for i, item in enumerate(items):
            if i == 0:
                continue
            new_sku = f"{base_sku}_mig{item.id}"[:64]
            item.sku = new_sku
            item.save(update_fields=["sku"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0004_inventorymovement_alter_inventoryitem_options_and_more"),
    ]

    operations = [
        migrations.RunPython(deduplicate_inventoryitem_sku, noop),
        migrations.AddField(
            model_name="inventoryitem",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
    ]
