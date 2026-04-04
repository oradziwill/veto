"""
Process VisitTranscriptionJob rows: Whisper + structuring + ClinicalExam update.
"""

from __future__ import annotations

import logging

from apps.medical.models import ClinicalExam
from apps.scheduling.models import VisitTranscriptionJob
from django.db import transaction

logger = logging.getLogger(__name__)


def process_visit_transcription_job(job_id: int) -> None:
    """
    Claim a pending job, run AI pipeline, update ClinicalExam, mark job completed/failed.

    No-op if job is missing or not pending (another worker may have claimed it).
    """
    with transaction.atomic():
        job = (
            VisitTranscriptionJob.objects.select_for_update(skip_locked=True)
            .filter(
                pk=job_id,
                status=VisitTranscriptionJob.Status.PENDING,
            )
            .first()
        )
        if job is None:
            return
        job.status = VisitTranscriptionJob.Status.PROCESSING
        job.save(update_fields=["status", "updated_at"])

    job.refresh_from_db()

    from .visit_transcription import (
        SUMMARY_UNKNOWN,
        VisitTranscriptionError,
        enforce_strict_summary,
        structure_transcript_with_claude,
        transcribe_audio_with_whisper,
    )

    try:
        with job.audio.open("rb") as audio_f:
            audio_bytes = audio_f.read()
        if not audio_bytes:
            raise VisitTranscriptionError("Stored audio file is empty.")

        transcript = transcribe_audio_with_whisper(
            audio_bytes=audio_bytes,
            filename=job.original_filename or f"visit-{job.appointment_id}.webm",
            content_type=job.content_type or "application/octet-stream",
        )
        structured_raw = structure_transcript_with_claude(transcript=transcript)
        structured, needs_review = enforce_strict_summary(
            transcript=transcript,
            structured=structured_raw,
        )
    except VisitTranscriptionError as exc:
        job.status = VisitTranscriptionJob.Status.FAILED
        job.last_error = str(exc)
        job.save(update_fields=["status", "last_error", "updated_at"])
        logger.warning("VisitTranscriptionJob %s failed: %s", job_id, exc)
        return
    except Exception as exc:  # pragma: no cover - defensive
        job.status = VisitTranscriptionJob.Status.FAILED
        job.last_error = str(exc)
        job.save(update_fields=["status", "last_error", "updated_at"])
        logger.exception("VisitTranscriptionJob %s unexpected error", job_id)
        return

    appointment = job.appointment
    exam, _created = ClinicalExam.objects.get_or_create(
        clinic_id=job.clinic_id,
        appointment=appointment,
        defaults={"created_by": job.created_by},
    )
    exam.transcript = transcript
    exam.ai_notes_raw = {
        **structured,
        "_strict_mode": True,
        "_needs_review": needs_review,
        "_unknown_fields": [k for k, v in structured.items() if v == SUMMARY_UNKNOWN],
    }
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

    unknown_fields = [k for k, v in structured.items() if v == SUMMARY_UNKNOWN]
    job.transcript = transcript
    job.structured = structured
    job.needs_review = needs_review
    job.unknown_fields = unknown_fields
    job.status = VisitTranscriptionJob.Status.COMPLETED
    job.last_error = ""

    try:
        if job.audio:
            job.audio.delete(save=False)
    except OSError:
        logger.warning("Could not delete audio file for VisitTranscriptionJob %s", job_id)
    job.audio = None

    job.save(
        update_fields=[
            "transcript",
            "structured",
            "needs_review",
            "unknown_fields",
            "status",
            "last_error",
            "audio",
            "updated_at",
        ]
    )
