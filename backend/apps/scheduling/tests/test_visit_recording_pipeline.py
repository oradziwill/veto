from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from apps.medical.models import ClinicalExam
from apps.scheduling.models import VisitRecording
from apps.scheduling.services.visit_transcription import SUMMARY_UNKNOWN, enforce_strict_summary
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command


@pytest.mark.django_db
def test_visit_recording_upload_creates_row(api_client, doctor, appointment, settings):
    settings.VISIT_RECORDINGS_S3_BUCKET = "recordings-bucket"
    settings.VISIT_RECORDINGS_PROCESS_INLINE_ON_UPLOAD = False
    mock_s3 = MagicMock()

    with patch(
        "apps.scheduling.views_recording_helpers._get_recording_s3_client",
        return_value=mock_s3,
    ):
        api_client.force_authenticate(user=doctor)
        upload = SimpleUploadedFile("visit.webm", b"fake-bytes", content_type="audio/webm")
        response = api_client.post(
            f"/api/visits/{appointment.id}/recordings/upload/",
            {"file": upload},
            format="multipart",
        )

    assert response.status_code == 201
    payload = response.json()
    row = VisitRecording.objects.get(pk=payload["id"])
    assert row.status == VisitRecording.Status.UPLOADED
    assert row.input_s3_key.startswith("visit_recordings/")
    mock_s3.upload_fileobj.assert_called_once()


@pytest.mark.django_db
def test_visit_recording_upload_inline_processing(api_client, doctor, appointment, settings):
    settings.VISIT_RECORDINGS_S3_BUCKET = "recordings-bucket"
    settings.VISIT_RECORDINGS_PROCESS_INLINE_ON_UPLOAD = True
    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": io.BytesIO(b"audio-bytes")}

    with patch(
        "apps.scheduling.views_recording_helpers._get_recording_s3_client",
        return_value=mock_s3,
    ):
        with patch(
            "apps.scheduling.views_visit_recordings.process_visit_recording",
            side_effect=lambda recording, audio_bytes: VisitRecording.objects.filter(
                pk=recording.pk
            ).update(
                status=VisitRecording.Status.READY,
                transcript="t",
                summary_text="s",
                summary_structured={"diagnosis": "x"},
                last_error="",
            ),
        ):
            api_client.force_authenticate(user=doctor)
            upload = SimpleUploadedFile("visit.webm", b"fake-bytes", content_type="audio/webm")
            response = api_client.post(
                f"/api/visits/{appointment.id}/recordings/upload/",
                {"file": upload},
                format="multipart",
            )

    assert response.status_code == 201
    row = VisitRecording.objects.get(pk=response.json()["id"])
    assert row.status == VisitRecording.Status.READY


@pytest.mark.django_db
def test_process_visit_recordings_command_sets_ready(
    clinic, patient, doctor, appointment, settings
):
    settings.VISIT_RECORDINGS_S3_BUCKET = "recordings-bucket"
    settings.VISIT_RECORDINGS_S3_REGION = "us-east-1"
    row = VisitRecording.objects.create(
        clinic=clinic,
        appointment=appointment,
        uploaded_by=doctor,
        original_filename="visit.webm",
        content_type="audio/webm",
        status=VisitRecording.Status.UPLOADED,
        input_s3_key="visit_recordings/abc/visit.webm",
    )

    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": io.BytesIO(b"audio")}
    with patch(
        "apps.scheduling.management.commands.process_visit_recordings.get_s3_client",
        return_value=mock_s3,
    ):
        with patch(
            "apps.scheduling.management.commands.process_visit_recordings.process_visit_recording"
        ) as process_mock:
            process_mock.side_effect = lambda recording, audio_bytes: VisitRecording.objects.filter(
                pk=recording.pk
            ).update(
                status=VisitRecording.Status.READY,
                transcript="Owner reports cough.",
                summary_text="Diagnosis: kennel cough",
                summary_structured={"diagnosis": "kennel cough"},
                last_error="",
            )
            call_command("process_visit_recordings", "--recording-id", str(row.id))

    row.refresh_from_db()
    assert row.status == VisitRecording.Status.READY


@pytest.mark.django_db
def test_visit_recording_detail_and_list(api_client, doctor, clinic, appointment):
    row = VisitRecording.objects.create(
        clinic=clinic,
        appointment=appointment,
        uploaded_by=doctor,
        original_filename="visit.webm",
        content_type="audio/webm",
        status=VisitRecording.Status.UPLOADED,
        input_s3_key="visit_recordings/abc/visit.webm",
    )
    api_client.force_authenticate(user=doctor)

    list_response = api_client.get(f"/api/visits/{appointment.id}/recordings/")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == row.id

    detail_response = api_client.get(f"/api/visit-recordings/{row.id}/")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == row.id


@pytest.mark.django_db
def test_process_visit_recordings_updates_clinical_exam(
    clinic, patient, doctor, appointment, settings
):
    settings.VISIT_RECORDINGS_S3_BUCKET = "recordings-bucket"
    row = VisitRecording.objects.create(
        clinic=clinic,
        appointment=appointment,
        uploaded_by=doctor,
        original_filename="visit.webm",
        content_type="audio/webm",
        status=VisitRecording.Status.UPLOADED,
        input_s3_key="visit_recordings/abc/visit.webm",
    )
    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": io.BytesIO(b"audio")}

    with patch(
        "apps.scheduling.management.commands.process_visit_recordings.get_s3_client",
        return_value=mock_s3,
    ):
        with patch(
            "apps.scheduling.services.visit_recording_pipeline.transcribe_audio_with_whisper",
            return_value=(
                "Owner reports lethargy and poor appetite for 2 days. "
                "Mild fever. "
                "Suspected infection. "
                "Antibiotic 5 days. "
                "Return if no improvement in 48h."
            ),
        ):
            with patch(
                "apps.scheduling.services.visit_recording_pipeline.structure_transcript_with_claude",
                return_value={
                    "anamnesis": "Lethargy and poor appetite for 2 days.",
                    "clinical_findings": "Mild fever.",
                    "diagnosis": "Suspected infection.",
                    "treatment_plan": "Antibiotic 5 days.",
                    "owner_instructions": "Return if no improvement in 48h.",
                },
            ):
                call_command("process_visit_recordings", "--recording-id", str(row.id))

    row.refresh_from_db()
    exam = ClinicalExam.objects.get(appointment=appointment)
    assert row.status == VisitRecording.Status.READY
    assert "Suspected infection" in row.summary_text
    assert exam.initial_diagnosis == "Suspected infection"


def test_enforce_strict_summary_replaces_non_grounded_with_unknown():
    transcript = "Owner reports cough. Mild fever."
    structured = {
        "anamnesis": "Owner reports cough.",
        "clinical_findings": "Mild fever.",
        "diagnosis": "Bacterial pneumonia.",
        "treatment_plan": "Antibiotic 7 days.",
        "owner_instructions": "Recheck in 2 days.",
    }
    strict, needs_review = enforce_strict_summary(transcript=transcript, structured=structured)
    assert strict["anamnesis"] == "Owner reports cough"
    assert strict["clinical_findings"] == "Mild fever"
    assert strict["diagnosis"] == SUMMARY_UNKNOWN
    assert strict["treatment_plan"] == SUMMARY_UNKNOWN
    assert strict["owner_instructions"] == SUMMARY_UNKNOWN
    assert needs_review is True
