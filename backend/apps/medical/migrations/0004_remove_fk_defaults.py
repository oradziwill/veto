from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("medical", "0003_clinicalexam_alter_medicalrecord_options_and_more"),
    ]

    operations = [
        # Re-declare these fields WITHOUT defaults at the migration layer.
        # This does not change data; it prevents unsafe implicit defaults in schema history.
        migrations.AlterField(
            model_name="medicalrecord",
            name="clinic",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="medical_records",
                related_query_name="medical_record",
                to="tenancy.clinic",
            ),
        ),
        migrations.AlterField(
            model_name="medicalrecord",
            name="patient",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="medical_records",
                to="patients.patient",
            ),
        ),
        migrations.AlterField(
            model_name="patienthistoryentry",
            name="record",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="history_entries",
                to="medical.medicalrecord",
            ),
        ),
    ]
