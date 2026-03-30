from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0004_clinic_online_booking_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="clinic",
            name="portal_booking_deposit_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                help_text="If > 0, portal bookings create a draft deposit invoice; visit stays scheduled until paid.",
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name="clinic",
            name="portal_booking_deposit_line_label",
            field=models.CharField(
                blank=True,
                default="Online booking deposit",
                max_length=255,
            ),
        ),
    ]
