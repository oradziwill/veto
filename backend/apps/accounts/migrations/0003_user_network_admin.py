# User.network + Role.NETWORK_ADMIN

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_add_user_role"),
        ("tenancy", "0007_clinic_network"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="network",
            field=models.ForeignKey(
                blank=True,
                help_text="Set for network_admin users; scopes access to all clinics in this network.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="network_users",
                to="tenancy.clinicnetwork",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("doctor", "Doctor"),
                    ("receptionist", "Receptionist"),
                    ("admin", "Clinic Admin"),
                    ("network_admin", "Network Admin"),
                ],
                default="receptionist",
                max_length=20,
            ),
        ),
    ]
