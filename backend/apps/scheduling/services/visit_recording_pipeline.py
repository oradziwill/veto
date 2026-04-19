from __future__ import annotations

import logging

from apps.medical.models import ClinicalExam, MedicalRecord, PatientHistoryEntry
from apps.scheduling.models import VisitRecording
from apps.scheduling.services.visit_transcription import (
    SUMMARY_UNKNOWN,
    VisitTranscriptionError,
    enforce_strict_summary,
    structure_transcript_with_claude,
    summarize_visit_for_history,
    transcribe_audio_with_whisper,
)
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


def get_recordings_bucket() -> str:
    bucket = str(getattr(settings, "VISIT_RECORDINGS_S3_BUCKET", "")).strip()
    if bucket:
        return bucket
    return str(getattr(settings, "DOCUMENTS_DATA_S3_BUCKET", "")).strip()


def format_summary(structured: dict[str, str]) -> str:
    return (
        f"Anamnesis: {structured.get('anamnesis', '').strip()}\n\n"
        f"Clinical findings: {structured.get('clinical_findings', '').strip()}\n\n"
        f"Diagnosis: {structured.get('diagnosis', '').strip()}\n\n"
        f"Treatment plan: {structured.get('treatment_plan', '').strip()}\n\n"
        f"Owner instructions: {structured.get('owner_instructions', '').strip()}"
    ).strip()


def process_visit_recording(*, recording: VisitRecording, audio_bytes: bytes) -> None:
    transcript = transcribe_audio_with_whisper(
        audio_bytes=audio_bytes,
        filename=recording.original_filename or f"visit-{recording.appointment_id}.webm",
        content_type=recording.content_type or "application/octet-stream",
    )
    structured_raw = structure_transcript_with_claude(transcript=transcript)
    structured, needs_review = enforce_strict_summary(
        transcript=transcript,
        structured=structured_raw,
    )
    summary_text = format_summary(structured)
    strict_metadata = {
        "_strict_mode": True,
        "_needs_review": needs_review,
        "_unknown_fields": [k for k, v in structured.items() if v == SUMMARY_UNKNOWN],
    }
    structured_for_storage = {**structured, **strict_metadata}

    with transaction.atomic():
        exam, _created = ClinicalExam.objects.get_or_create(
            clinic_id=recording.clinic_id,
            appointment_id=recording.appointment_id,
            defaults={"created_by_id": recording.uploaded_by_id},
        )
        exam.transcript = transcript
        exam.ai_notes_raw = structured_for_storage
        exam.initial_notes = structured.get("anamnesis", "")
        exam.clinical_examination = structured.get("clinical_findings", "")
        exam.initial_diagnosis = structured.get("diagnosis", "")
        exam.additional_notes = structured.get("treatment_plan", "")
        exam.owner_instructions = structured.get("owner_instructions", "")
        exam.save(
            update_fields=[
                "transcript",
                "ai_notes_raw",
                "initial_notes",
                "clinical_examination",
                "initial_diagnosis",
                "additional_notes",
                "owner_instructions",
                "updated_at",
            ]
        )

        recording.transcript = transcript
        recording.summary_structured = structured_for_storage
        recording.summary_text = summary_text
        recording.status = VisitRecording.Status.READY
        recording.last_error = ""
        recording.save(
            update_fields=[
                "transcript",
                "summary_structured",
                "summary_text",
                "status",
                "last_error",
                "updated_at",
            ]
        )

        try:
            appointment = recording.appointment
            patient = appointment.patient
            medical_record, _ = MedicalRecord.objects.get_or_create(
                clinic_id=recording.clinic_id,
                patient=patient,
                defaults={"created_by_id": recording.uploaded_by_id},
            )
            if not PatientHistoryEntry.objects.filter(
                clinic_id=recording.clinic_id,
                appointment=appointment,
            ).exists():
                summary_note = summarize_visit_for_history(structured=structured)
                if summary_note:
                    PatientHistoryEntry.objects.create(
                        clinic_id=recording.clinic_id,
                        record=medical_record,
                        appointment=appointment,
                        note=summary_note,
                        created_by_id=recording.uploaded_by_id,
                    )
        except Exception:
            logger.exception(
                "Failed to save visit summary to patient history for recording %s",
                recording.pk,
            )


def safe_error_text(exc: Exception, *, max_len: int = 4000) -> str:
    if isinstance(exc, VisitTranscriptionError):
        text = str(exc)
    else:
        text = f"{exc.__class__.__name__}: {exc}"
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 20] + "\n…(truncated)"
