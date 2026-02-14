# Generated manually for add_user_role

from django.db import migrations, models


def set_role_from_is_vet_and_staff(apps, schema_editor):
    """Migrate existing users: is_vet->doctor, is_staff and not is_vet->admin, else receptionist."""
    User = apps.get_model("accounts", "User")
    for user in User.objects.all():
        if user.is_vet:
            user.role = "doctor"
        elif user.is_staff:
            user.role = "admin"
        else:
            user.role = "receptionist"
        user.save(update_fields=["role"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("doctor", "Doctor"),
                    ("receptionist", "Receptionist"),
                    ("admin", "Clinic Admin"),
                ],
                default="receptionist",
                max_length=20,
            ),
            preserve_default=True,
        ),
        migrations.RunPython(set_role_from_is_vet_and_staff, migrations.RunPython.noop),
    ]
