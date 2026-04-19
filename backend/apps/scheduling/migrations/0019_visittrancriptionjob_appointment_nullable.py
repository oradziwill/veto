import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scheduling", "0018_visit_transcription_job"),
    ]

    operations = [
        migrations.AlterField(
            model_name="visittranscriptionjob",
            name="appointment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="visit_transcription_jobs",
                to="scheduling.appointment",
            ),
        ),
    ]
