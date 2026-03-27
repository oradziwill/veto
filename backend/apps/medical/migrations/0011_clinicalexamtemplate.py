from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("medical", "0010_clinicalexam_weight_kg"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ClinicalExamTemplate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                ("visit_type", models.CharField(blank=True, default="", max_length=40)),
                ("defaults", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "clinic",
                    models.ForeignKey(
                        on_delete=models.PROTECT,
                        related_name="clinical_exam_templates",
                        to="tenancy.clinic",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="created_clinical_exam_templates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.AddConstraint(
            model_name="clinicalexamtemplate",
            constraint=models.UniqueConstraint(
                fields=("clinic", "name"),
                name="medical_clinical_exam_template_name_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="clinicalexamtemplate",
            index=models.Index(
                fields=["clinic", "is_active"],
                name="medical_clinical_tpl_active_idx",
            ),
        ),
    ]
