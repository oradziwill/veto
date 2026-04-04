from __future__ import annotations

import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsDoctorOrAdmin
from apps.scheduling.models import Appointment, VisitRecording, VisitTranscriptionJob
from apps.scheduling.serializers import (
    VisitRecordingSerializer,
    VisitRecordingUploadResponseSerializer,
)
from apps.scheduling.services.visit_recording_pipeline import (
    get_recordings_bucket,
    process_visit_recording,
    safe_error_text,
)
from apps.scheduling.services.visit_transcription_job import process_visit_transcription_job
from apps.tenancy.access import accessible_clinic_ids

from . import views_recording_helpers as _recording_helpers


def _visit_transcription_job_payload(job: VisitTranscriptionJob) -> dict:
    """API shape for job status + completed transcription (matches legacy POST body)."""
    out: dict = {
        "id": job.id,
        "status": job.status,
    }
    if job.status == VisitTranscriptionJob.Status.FAILED:
        out["last_error"] = job.last_error or None
        return out
    if job.status == VisitTranscriptionJob.Status.COMPLETED:
        out["transcript"] = job.transcript
        out["structured"] = job.structured
        out["strict_mode"] = True
        out["needs_review"] = job.needs_review
        out["unknown_fields"] = list(job.unknown_fields or [])
        return out
    if job.status == VisitTranscriptionJob.Status.PROCESSING:
        out["detail"] = "Transcription in progress."
        return out
    out["detail"] = "Transcription queued. Poll GET until status is completed or failed."
    return out


class VisitTranscriptionView(APIView):
    permission_classes = [IsAuthenticated, HasClinic, IsDoctorOrAdmin]
    allowed_audio_types = {
        "audio/webm",
        "audio/ogg",
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
    }
    max_bytes = 25 * 1024 * 1024

    def post(self, request, appointment_id: int):
        appointment = (
            Appointment.objects.filter(
                id=appointment_id, clinic_id__in=accessible_clinic_ids(request.user)
            )
            .select_related("patient")
            .first()
        )
        if not appointment:
            return Response({"detail": "Appointment not found."}, status=404)

        upload = request.FILES.get("audio")
        if upload is None:
            return Response(
                {"detail": "Missing audio file in multipart field 'audio'."}, status=400
            )
        if upload.size > self.max_bytes:
            return Response({"detail": "Audio file exceeds 25MB limit."}, status=400)
        if (upload.content_type or "").lower() not in self.allowed_audio_types:
            return Response(
                {"detail": "Unsupported audio content type. Allowed: webm, ogg, wav, mp3."},
                status=400,
            )

        audio_bytes = upload.read()
        if not audio_bytes:
            return Response({"detail": "Uploaded audio file is empty."}, status=400)

        inline = bool(getattr(settings, "VISIT_TRANSCRIPTION_INLINE_PROCESSING", False))
        safe_name = _recording_helpers._safe_s3_filename(
            upload.name or f"visit-{appointment_id}.webm"
        )
        job = VisitTranscriptionJob(
            clinic_id=appointment.clinic_id,
            appointment=appointment,
            created_by=request.user,
            status=VisitTranscriptionJob.Status.PENDING,
            original_filename=upload.name or safe_name,
            content_type=upload.content_type or "",
            size_bytes=upload.size,
        )
        job.audio.save(safe_name, ContentFile(audio_bytes), save=False)
        job.save()

        if inline:
            process_visit_transcription_job(job.id)
            job.refresh_from_db()
            if job.status == VisitTranscriptionJob.Status.FAILED:
                return Response(
                    {"detail": job.last_error or "Transcription failed."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            return Response(_visit_transcription_job_payload(job), status=200)

        detail_url = request.build_absolute_uri(
            f"/api/visits/{appointment_id}/transcribe/jobs/{job.id}/"
        )
        body = _visit_transcription_job_payload(job)
        body["job_url"] = detail_url
        return Response(body, status=202)


class VisitTranscriptionJobDetailView(APIView):
    permission_classes = [IsAuthenticated, HasClinic, IsDoctorOrAdmin]

    def get(self, request, appointment_id: int, job_id: int):
        allowed = accessible_clinic_ids(request.user)
        job = VisitTranscriptionJob.objects.filter(
            pk=job_id,
            appointment_id=appointment_id,
            clinic_id__in=allowed,
        ).first()
        if not job:
            return Response({"detail": "Transcription job not found."}, status=404)
        return Response(_visit_transcription_job_payload(job), status=200)


class VisitRecordingUploadView(APIView):
    permission_classes = [IsAuthenticated, HasClinic, IsDoctorOrAdmin]
    allowed_types = {
        "audio/webm",
        "audio/ogg",
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "video/webm",
        "video/mp4",
    }

    def post(self, request, appointment_id: int):
        appointment = (
            Appointment.objects.filter(
                id=appointment_id, clinic_id__in=accessible_clinic_ids(request.user)
            )
            .select_related("patient")
            .first()
        )
        if not appointment:
            return Response({"detail": "Appointment not found."}, status=404)

        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "Missing file in multipart field 'file'."}, status=400)

        max_mb = int(getattr(settings, "VISIT_RECORDINGS_MAX_UPLOAD_MB", 200))
        if upload.size > max_mb * 1024 * 1024:
            return Response({"detail": f"Recording exceeds {max_mb}MB limit."}, status=400)
        content_type = (upload.content_type or "").lower()
        if content_type not in self.allowed_types:
            return Response(
                {"detail": "Unsupported media type. Allowed: webm, wav, ogg, mp3, mp4."},
                status=400,
            )

        bucket = get_recordings_bucket()
        if not bucket:
            return Response(
                {
                    "detail": (
                        "Recording storage is not configured. Set VISIT_RECORDINGS_S3_BUCKET "
                        "or DOCUMENTS_DATA_S3_BUCKET."
                    )
                },
                status=400,
            )

        safe_filename = _recording_helpers._safe_s3_filename(upload.name or "recording.webm")
        job_id = uuid.uuid4()
        input_s3_key = f"visit_recordings/{job_id}/{safe_filename}"

        try:
            _recording_helpers._get_recording_s3_client().upload_fileobj(
                upload,
                bucket,
                input_s3_key,
                ExtraArgs={"ContentType": upload.content_type or "application/octet-stream"},
            )
        except Exception as exc:
            return Response({"detail": f"Upload to storage failed: {exc}"}, status=400)

        with transaction.atomic():
            recording = VisitRecording.objects.create(
                clinic_id=appointment.clinic_id,
                appointment=appointment,
                uploaded_by=request.user,
                original_filename=upload.name or "recording.webm",
                content_type=upload.content_type or "",
                size_bytes=upload.size,
                status=VisitRecording.Status.UPLOADED,
                input_s3_key=input_s3_key,
                job_id=job_id,
            )

        process_inline = bool(getattr(settings, "VISIT_RECORDINGS_PROCESS_INLINE_ON_UPLOAD", False))
        if process_inline:
            claimed = VisitRecording.objects.filter(
                pk=recording.pk,
                status=VisitRecording.Status.UPLOADED,
            ).update(status=VisitRecording.Status.PROCESSING)
            if claimed == 1:
                try:
                    response = _recording_helpers._get_recording_s3_client().get_object(
                        Bucket=bucket, Key=input_s3_key
                    )
                    audio_bytes = response["Body"].read()
                    recording.refresh_from_db()
                    process_visit_recording(recording=recording, audio_bytes=audio_bytes)
                except Exception as exc:
                    recording.refresh_from_db()
                    recording.status = VisitRecording.Status.FAILED
                    recording.last_error = safe_error_text(exc)
                    recording.save(update_fields=["status", "last_error", "updated_at"])

        try:
            _recording_helpers._trigger_visit_recording_uploaded(recording.id)
        except Exception:
            # Best-effort only; processing can still be done by command/scheduler.
            pass

        return Response(VisitRecordingUploadResponseSerializer(recording).data, status=201)


class VisitRecordingListView(APIView):
    permission_classes = [IsAuthenticated, HasClinic, IsDoctorOrAdmin]

    def get(self, request, appointment_id: int):
        appointment = Appointment.objects.filter(
            id=appointment_id,
            clinic_id__in=accessible_clinic_ids(request.user),
        ).first()
        if not appointment:
            return Response({"detail": "Appointment not found."}, status=404)
        items = VisitRecording.objects.filter(
            appointment_id=appointment.id,
            clinic_id__in=accessible_clinic_ids(request.user),
        ).order_by("-created_at")
        return Response(VisitRecordingSerializer(items, many=True).data, status=200)


class VisitRecordingDetailView(APIView):
    permission_classes = [IsAuthenticated, HasClinic, IsDoctorOrAdmin]

    def get(self, request, recording_id: int):
        item = VisitRecording.objects.filter(
            id=recording_id,
            clinic_id__in=accessible_clinic_ids(request.user),
        ).first()
        if not item:
            return Response({"detail": "Visit recording not found."}, status=404)
        return Response(VisitRecordingSerializer(item).data, status=200)
