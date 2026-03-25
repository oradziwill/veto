from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0002_set_service_db_table"),
    ]

    operations = [
        # Invoice: add invoice_number, ksef_number, ksef_status
        migrations.AddField(
            model_name="invoice",
            name="invoice_number",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="invoice",
            name="ksef_number",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="ksef_status",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        # InvoiceLine: change quantity to DecimalField, add vat_rate and unit
        migrations.AlterField(
            model_name="invoiceline",
            name="quantity",
            field=models.DecimalField(decimal_places=3, default=Decimal("1"), max_digits=10),
        ),
        migrations.AddField(
            model_name="invoiceline",
            name="vat_rate",
            field=models.CharField(
                choices=[
                    ("23", "23%"),
                    ("8", "8%"),
                    ("5", "5%"),
                    ("0", "0%"),
                    ("zw", "Zwolniony (zw)"),
                    ("oo", "Odwrotne obciążenie (oo)"),
                    ("np", "Poza VAT (np)"),
                ],
                default="8",
                max_length=4,
            ),
        ),
        migrations.AddField(
            model_name="invoiceline",
            name="unit",
            field=models.CharField(default="usł", max_length=20),
        ),
    ]
