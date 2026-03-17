from __future__ import annotations

from datetime import timedelta

import pytest
from apps.medical.models import ClinicalExam
from apps.scheduling.models import Appointment
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone


@pytest.mark.django_db
def test_visit_transcription_endpoint_requires_doctor_or_admin(
    api_client, receptionist, appointment
):
    api_client.force_authenticate(user=receptionist)
    upload = SimpleUploadedFile("visit.wav", b"fake-bytes", content_type="audio/wav")
    response = api_client.post(
        f"/api/visits/{appointment.id}/transcribe/",
        {"audio": upload},
        format="multipart",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_visit_transcription_endpoint_happy_path_creates_or_updates_exam(
    api_client, doctor, clinic, patient
):
    starts_at = timezone.now() + timedelta(hours=2)
    appointment = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
        status=Appointment.Status.SCHEDULED,
    )
    api_client.force_authenticate(user=doctor)

    def _fake_whisper(**_kwargs):
        return "Owner reports vomiting for two days."

    def _fake_claude(*, transcript):
        assert "vomiting" in transcript
        return {
            "anamnesis": "Owner reports vomiting for two days.",
            "clinical_findings": "Mild dehydration, temp 38.5C.",
            "diagnosis": "Suspected gastroenteritis.",
            "treatment_plan": "Metronidazole 250mg BID for 5 days.",
            "owner_instructions": "Bland diet for 3 days.",
        }

    from apps.scheduling import views as scheduling_views

    scheduling_views.transcribe_audio_with_whisper = _fake_whisper
    scheduling_views.structure_transcript_with_claude = _fake_claude

    upload = SimpleUploadedFile("visit.wav", b"fake-audio-content", content_type="audio/wav")
    response = api_client.post(
        f"/api/visits/{appointment.id}/transcribe/",
        {"audio": upload},
        format="multipart",
    )
    assert response.status_code == 200
    assert response.data["transcript"].startswith("Owner reports")
    assert "structured" in response.data
    assert response.data["structured"]["diagnosis"] == "Suspected gastroenteritis."

    exam = ClinicalExam.objects.get(appointment=appointment)
    assert exam.transcript.startswith("Owner reports")
    assert exam.ai_notes_raw["clinical_findings"] == "Mild dehydration, temp 38.5C."
    assert exam.initial_diagnosis == "Suspected gastroenteritis."
    assert exam.owner_instructions == "Bland diet for 3 days."


@pytest.mark.django_db
def test_visit_transcription_rejects_missing_or_invalid_audio(api_client, doctor, appointment):
    api_client.force_authenticate(user=doctor)
    missing = api_client.post(
        f"/api/visits/{appointment.id}/transcribe/",
        {},
        format="multipart",
    )
    assert missing.status_code == 400

    invalid_upload = SimpleUploadedFile("visit.txt", b"text", content_type="text/plain")
    invalid = api_client.post(
        f"/api/visits/{appointment.id}/transcribe/",
        {"audio": invalid_upload},
        format="multipart",
    )
    assert invalid.status_code == 400
