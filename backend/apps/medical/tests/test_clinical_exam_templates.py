import pytest
from apps.medical.models import ClinicalExamTemplate


@pytest.mark.django_db
def test_doctor_can_create_and_list_clinical_exam_templates(api_client, doctor):
    api_client.force_authenticate(user=doctor)

    create = api_client.post(
        "/api/medical/clinical-exam-templates/",
        {
            "name": "Dermatology default",
            "visit_type": "dermatology",
            "defaults": {
                "clinical_examination": "Skin and coat inspection completed.",
                "owner_instructions": "Monitor pruritus and return in 7 days.",
            },
            "is_active": True,
        },
        format="json",
    )
    assert create.status_code == 201
    assert create.data["name"] == "Dermatology default"

    listing = api_client.get("/api/medical/clinical-exam-templates/")
    assert listing.status_code == 200
    assert len(listing.data) >= 1
    names = [item["name"] for item in listing.data]
    assert "Dermatology default" in names


@pytest.mark.django_db
def test_apply_exam_template_prefills_empty_fields_without_overwrite(
    api_client, doctor, appointment
):
    template = ClinicalExamTemplate.objects.create(
        clinic=doctor.clinic,
        name="Standard exam",
        defaults={
            "initial_notes": "Template initial note",
            "clinical_examination": "Template exam section",
            "owner_instructions": "Template owner instructions",
        },
        is_active=True,
        created_by=doctor,
    )
    api_client.force_authenticate(user=doctor)

    first_apply = api_client.post(
        f"/api/appointments/{appointment.id}/exam/apply-template/",
        {"template_id": template.id},
        format="json",
    )
    assert first_apply.status_code == 200
    assert first_apply.data["initial_notes"] == "Template initial note"
    assert first_apply.data["template_meta"]["template_id"] == template.id

    patch_exam = api_client.patch(
        f"/api/appointments/{appointment.id}/exam/",
        {"initial_notes": "Doctor custom note"},
        format="json",
    )
    assert patch_exam.status_code == 200

    second_apply = api_client.post(
        f"/api/appointments/{appointment.id}/exam/apply-template/",
        {"template_id": template.id},
        format="json",
    )
    assert second_apply.status_code == 200
    assert second_apply.data["initial_notes"] == "Doctor custom note"
    assert "initial_notes" not in second_apply.data["template_meta"]["applied_fields"]
