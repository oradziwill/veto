from __future__ import annotations

import csv
import json
import re
import uuid
from datetime import date as date_type
from datetime import timedelta
from io import StringIO

import boto3
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsDoctorOrAdmin, IsStaffOrVet
from apps.audit.services import log_audit_event
from apps.medical.models import ClinicalExam
from apps.medical.serializers import (
    ClinicalExamReadSerializer,
    ClinicalExamWriteSerializer,
)
from apps.patients.models import Patient
from apps.scheduling.models import (
    Appointment,
    HospitalDischargeSummary,
    HospitalMedicationAdministration,
    HospitalMedicationOrder,
    HospitalStay,
    HospitalStayNote,
    HospitalStayTask,
    Room,
    VisitRecording,
    WaitingQueueEntry,
)
from apps.scheduling.serializers import (
    AppointmentReadSerializer,
    AppointmentWriteSerializer,
    HospitalDischargeSummaryReadSerializer,
    HospitalDischargeSummaryWriteSerializer,
    HospitalMedicationAdministrationReadSerializer,
    HospitalMedicationAdministrationWriteSerializer,
    HospitalMedicationOrderReadSerializer,
    HospitalMedicationOrderWriteSerializer,
    HospitalStayNoteReadSerializer,
    HospitalStayNoteWriteSerializer,
    HospitalStayReadSerializer,
    HospitalStayTaskReadSerializer,
    HospitalStayTaskWriteSerializer,
    HospitalStayWriteSerializer,
    RoomSerializer,
    VisitRecordingSerializer,
    VisitRecordingUploadResponseSerializer,
    WaitingQueueEntryReadSerializer,
    WaitingQueueEntryWriteSerializer,
)
from apps.scheduling.services.availability import compute_availability
from apps.scheduling.services.discharge_pdf import render_discharge_summary_pdf_bytes
from apps.scheduling.services.visit_recording_pipeline import (
    get_recordings_bucket,
    process_visit_recording,
    safe_error_text,
)
from apps.scheduling.services.visit_transcription import (
    SUMMARY_UNKNOWN,
    VisitTranscriptionError,
    enforce_strict_summary,
    structure_transcript_with_claude,
    transcribe_audio_with_whisper,
)


def _safe_s3_filename(original: str) -> str:
    name = original or "recording"
    stem, dot, suffix = name.rpartition(".")
    if not dot:
        stem = name
        suffix = ""
    safe_stem = re.sub(r"[^\w\-.]", "_", stem)[:200]
    safe_suffix = re.sub(r"[^\w]", "", suffix)[:10]
    return (safe_stem or "recording") + (f".{safe_suffix}" if safe_suffix else "")


def _get_recording_s3_client():
    region = getattr(settings, "VISIT_RECORDINGS_S3_REGION", "") or getattr(
        settings, "DOCUMENTS_S3_REGION", "us-east-1"
    )
    return boto3.client("s3", region_name=region)


def _get_eventbridge_client():
    region = getattr(settings, "VISIT_RECORDINGS_S3_REGION", "") or getattr(
        settings, "DOCUMENTS_S3_REGION", "us-east-1"
    )
    return boto3.client("events", region_name=region)


def _trigger_visit_recording_uploaded(recording_id: int) -> None:
    detail = json.dumps({"visit_recording_id": int(recording_id)})
    _get_eventbridge_client().put_events(
        Entries=[
            {
                "Source": "veto.scheduling",
                "DetailType": "visit_recording_uploaded",
                "Detail": detail,
            }
        ]
    )


class AppointmentViewSet(viewsets.ModelViewSet):
    """
    CRUD for appointments within the user's clinic.
    Supports filtering by date, vet, patient, and status.
    """

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        user = self.request.user

        qs = (
            Appointment.objects.filter(clinic_id=user.clinic_id)
            .select_related("clinic", "patient", "vet", "room")
            .order_by("starts_at")
        )

        # Optional filters
        day = self.request.query_params.get("date")
        if day:
            try:
                parsed = parse_date(day)
            except ValueError:
                parsed = None
            if parsed:
                qs = qs.filter(starts_at__date=parsed)

        date_from = self.request.query_params.get("date_from")
        if date_from:
            try:
                parsed_from = parse_date(date_from)
            except ValueError:
                parsed_from = None
            if parsed_from:
                qs = qs.filter(starts_at__date__gte=parsed_from)

        date_to = self.request.query_params.get("date_to")
        if date_to:
            try:
                parsed_to = parse_date(date_to)
            except ValueError:
                parsed_to = None
            if parsed_to:
                qs = qs.filter(starts_at__date__lte=parsed_to)

        vet_id = self.request.query_params.get("vet")
        if vet_id:
            qs = qs.filter(vet_id=vet_id)

        patient_id = self.request.query_params.get("patient")
        if patient_id:
            qs = qs.filter(patient_id=patient_id)

        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)

        visit_type = self.request.query_params.get("visit_type")
        if visit_type:
            qs = qs.filter(visit_type=visit_type)

        return qs

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return AppointmentReadSerializer
        return AppointmentWriteSerializer

    @staticmethod
    def _build_visit_readiness_payload(appt: Appointment, exam: ClinicalExam | None) -> dict:
        ai_notes = exam.ai_notes_raw if exam and isinstance(exam.ai_notes_raw, dict) else {}
        unknown_fields = ai_notes.get("_unknown_fields", [])
        if not isinstance(unknown_fields, list):
            unknown_fields = []

        needs_review = bool(ai_notes.get("_needs_review", False))
        has_exam = exam is not None
        can_close = has_exam

        reasons: list[str] = []
        if not has_exam:
            reasons.append("clinical_exam_missing")
        if needs_review:
            reasons.append("ai_summary_needs_review")
        if unknown_fields:
            reasons.append("ai_summary_has_unknown_fields")

        return {
            "appointment_id": appt.id,
            "appointment_status": appt.status,
            "can_close_visit": can_close,
            "has_clinical_exam": has_exam,
            "needs_review": needs_review,
            "unknown_fields": unknown_fields,
            "blocking_reasons": reasons if not can_close else [],
            "warnings": reasons if can_close else [],
        }

    def perform_create(self, serializer):
        appointment = serializer.save(clinic=self.request.user.clinic)
        if appointment.status == Appointment.Status.CANCELLED and appointment.cancelled_at is None:
            appointment.cancelled_at = timezone.now()
            appointment.save(update_fields=["cancelled_at", "updated_at"])

        # Invalidate AI summary cache for the patient when a new visit is added
        if appointment.patient_id:
            patient = Patient.objects.get(pk=appointment.patient_id)
            patient.ai_summary = ""
            patient.ai_summary_updated_at = None
            patient.save(update_fields=["ai_summary", "ai_summary_updated_at"])

    def perform_update(self, serializer):
        old_status = serializer.instance.status if serializer.instance else None
        appointment = serializer.save(clinic=self.request.user.clinic)
        if appointment.status == Appointment.Status.CANCELLED and appointment.cancelled_at is None:
            appointment.cancelled_at = timezone.now()
            appointment.save(update_fields=["cancelled_at", "updated_at"])
        if old_status and old_status != appointment.status:
            log_audit_event(
                clinic_id=self.request.user.clinic_id,
                actor=self.request.user,
                action="appointment_status_changed",
                entity_type="appointment",
                entity_id=appointment.id,
                before={"status": old_status},
                after={"status": appointment.status},
            )

    @action(detail=False, methods=["get"], url_path="cancellation-analytics")
    def cancellation_analytics(self, request):
        """
        GET /api/appointments/cancellation-analytics/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
        Aggregate cancelled/no-show insights for operations.
        """
        date_from = parse_date(request.query_params.get("date_from") or "")
        date_to = parse_date(request.query_params.get("date_to") or "")
        if not date_to:
            date_to = timezone.localdate()
        if not date_from:
            date_from = date_to - timedelta(days=30)
        if date_from > date_to:
            return Response({"detail": "date_from cannot be after date_to."}, status=400)

        qs = Appointment.objects.filter(
            clinic_id=request.user.clinic_id,
            starts_at__date__gte=date_from,
            starts_at__date__lte=date_to,
            status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW],
        )

        totals = qs.aggregate(
            cancelled_count=Count("id", filter=Q(status=Appointment.Status.CANCELLED)),
            no_show_count=Count("id", filter=Q(status=Appointment.Status.NO_SHOW)),
            total_count=Count("id"),
        )

        by_vet = list(
            qs.values("vet_id", "vet__username", "vet__first_name", "vet__last_name")
            .annotate(
                cancelled_count=Count("id", filter=Q(status=Appointment.Status.CANCELLED)),
                no_show_count=Count("id", filter=Q(status=Appointment.Status.NO_SHOW)),
                total_count=Count("id"),
            )
            .order_by("-total_count", "vet_id")
        )
        for row in by_vet:
            full_name = f"{(row.get('vet__first_name') or '').strip()} {(row.get('vet__last_name') or '').strip()}".strip()
            row["vet_name"] = full_name or row.get("vet__username") or ""
            row.pop("vet__first_name", None)
            row.pop("vet__last_name", None)
            row.pop("vet__username", None)

        by_visit_type = list(
            qs.values("visit_type")
            .annotate(
                cancelled_count=Count("id", filter=Q(status=Appointment.Status.CANCELLED)),
                no_show_count=Count("id", filter=Q(status=Appointment.Status.NO_SHOW)),
                total_count=Count("id"),
            )
            .order_by("-total_count", "visit_type")
        )

        weekday_names = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        by_weekday_map = {
            name: {"weekday": name, "cancelled_count": 0, "no_show_count": 0, "total_count": 0}
            for name in weekday_names
        }
        for item in qs.values("starts_at", "status"):
            weekday = weekday_names[item["starts_at"].weekday()]
            by_weekday_map[weekday]["total_count"] += 1
            if item["status"] == Appointment.Status.CANCELLED:
                by_weekday_map[weekday]["cancelled_count"] += 1
            if item["status"] == Appointment.Status.NO_SHOW:
                by_weekday_map[weekday]["no_show_count"] += 1
        by_weekday = [by_weekday_map[name] for name in weekday_names]

        cancelled_source = {
            "client": 0,
            "clinic": 0,
            "unspecified": 0,
        }
        for item in qs.filter(status=Appointment.Status.CANCELLED).values("cancelled_by"):
            source = item["cancelled_by"] or ""
            if source == Appointment.CancelledBy.CLIENT:
                cancelled_source["client"] += 1
            elif source == Appointment.CancelledBy.CLINIC:
                cancelled_source["clinic"] += 1
            else:
                cancelled_source["unspecified"] += 1

        lead_time = {
            "under_24h": 0,
            "between_24h_48h": 0,
            "between_48h_7d": 0,
            "over_7d": 0,
            "unknown": 0,
        }
        cancelled_for_lead = qs.filter(status=Appointment.Status.CANCELLED).values(
            "starts_at", "cancelled_at"
        )
        for item in cancelled_for_lead:
            starts_at = item["starts_at"]
            cancelled_at = item["cancelled_at"]
            if not cancelled_at or cancelled_at > starts_at:
                lead_time["unknown"] += 1
                continue

            hours = (starts_at - cancelled_at).total_seconds() / 3600.0
            if hours < 24:
                lead_time["under_24h"] += 1
            elif hours < 48:
                lead_time["between_24h_48h"] += 1
            elif hours < 168:
                lead_time["between_48h_7d"] += 1
            else:
                lead_time["over_7d"] += 1

        payload = {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "totals": totals,
            "by_vet": by_vet,
            "by_visit_type": by_visit_type,
            "by_weekday": by_weekday,
            "cancelled_source": cancelled_source,
            "cancelled_lead_time": lead_time,
        }

        if (request.query_params.get("export") or "").strip().lower() == "csv":
            buffer = StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["section", "key", "value"])
            writer.writerow(["totals", "cancelled_count", totals["cancelled_count"]])
            writer.writerow(["totals", "no_show_count", totals["no_show_count"]])
            writer.writerow(["totals", "total_count", totals["total_count"]])
            for row in by_vet:
                writer.writerow(
                    ["by_vet", f"{row['vet_id']}:{row['vet_name']}", row["total_count"]]
                )
            for row in by_visit_type:
                writer.writerow(["by_visit_type", row["visit_type"], row["total_count"]])
            for row in by_weekday:
                writer.writerow(["by_weekday", row["weekday"], row["total_count"]])
            for key, value in cancelled_source.items():
                writer.writerow(["cancelled_source", key, value])
            for key, value in lead_time.items():
                writer.writerow(["cancelled_lead_time", key, value])

            response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = (
                f'attachment; filename="cancellation-analytics-{payload["date_from"]}-to-{payload["date_to"]}.csv"'
            )
            return response

        return Response(payload, status=200)

    @action(detail=True, methods=["get", "post", "patch"], url_path="exam")
    def exam(self, request, pk=None):
        """
        GET   /api/appointments/<id>/exam/   -> fetch exam (404 if none)
        POST  /api/appointments/<id>/exam/   -> create (400 if exists)
        PATCH /api/appointments/<id>/exam/   -> partial update
        """
        user = request.user
        appt = self.get_object()  # already clinic-scoped by queryset

        if request.method in ("POST", "PATCH") and not IsDoctorOrAdmin().has_permission(
            request, self
        ):
            raise PermissionDenied(
                "Only doctors and clinic admins can create/update clinical exam."
            )

        exam = (
            ClinicalExam.objects.filter(
                appointment_id=appt.id,
                clinic_id=user.clinic_id,
            )
            .order_by("id")
            .first()
        )

        if request.method == "GET":
            if not exam:
                return Response({"detail": "Not found."}, status=404)
            return Response(ClinicalExamReadSerializer(exam).data, status=200)

        if request.method == "POST":
            if exam:
                return Response({"detail": "Exam already exists."}, status=400)

            serializer = ClinicalExamWriteSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            exam = serializer.save(
                clinic_id=user.clinic_id,
                appointment=appt,
                created_by=user,
            )
            return Response(ClinicalExamReadSerializer(exam).data, status=201)

        # PATCH
        if not exam:
            return Response({"detail": "Not found."}, status=404)

        serializer = ClinicalExamWriteSerializer(exam, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        exam = serializer.save()
        return Response(ClinicalExamReadSerializer(exam).data, status=200)

    @action(detail=True, methods=["get"], url_path="visit-readiness")
    def visit_readiness(self, request, pk=None):
        """
        GET /api/appointments/<id>/visit-readiness/
        Returns backend readiness checks for closing a visit.
        """
        user = request.user
        appt = self.get_object()  # clinic-scoped
        exam = (
            ClinicalExam.objects.filter(
                appointment_id=appt.id,
                clinic_id=user.clinic_id,
            )
            .order_by("id")
            .first()
        )
        payload = self._build_visit_readiness_payload(appt=appt, exam=exam)
        return Response(payload, status=200)

    @action(detail=True, methods=["post"], url_path="close-visit")
    def close_visit(self, request, pk=None):
        """
        POST /api/appointments/<id>/close-visit/
        Vet-only: marks the appointment as completed.
        """
        appt = self.get_object()  # clinic-scoped

        if not IsDoctorOrAdmin().has_permission(request, self):
            raise PermissionDenied("Only doctors and clinic admins can close a visit.")

        require_exam = bool(getattr(settings, "REQUIRE_CLINICAL_EXAM_FOR_VISIT_CLOSE", False))
        if require_exam:
            exam = (
                ClinicalExam.objects.filter(
                    appointment_id=appt.id,
                    clinic_id=request.user.clinic_id,
                )
                .order_by("id")
                .first()
            )
            if not exam:
                return Response(
                    {
                        "detail": "Clinical exam is required before closing visit.",
                        "code": "clinical_exam_missing",
                    },
                    status=400,
                )

        # If your domain wants a different terminal status, adjust here.
        old_status = appt.status
        appt.status = "completed"
        appt.save(update_fields=["status"])
        log_audit_event(
            clinic_id=request.user.clinic_id,
            actor=request.user,
            action="visit_closed",
            entity_type="appointment",
            entity_id=appt.id,
            before={"status": old_status},
            after={"status": appt.status},
        )

        return Response(status=204)


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
            Appointment.objects.filter(id=appointment_id, clinic_id=request.user.clinic_id)
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

        try:
            transcript = transcribe_audio_with_whisper(
                audio_bytes=audio_bytes,
                filename=upload.name or f"visit-{appointment_id}.webm",
                content_type=upload.content_type or "application/octet-stream",
            )
            structured_raw = structure_transcript_with_claude(transcript=transcript)
            structured, needs_review = enforce_strict_summary(
                transcript=transcript,
                structured=structured_raw,
            )
        except VisitTranscriptionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        exam, _created = ClinicalExam.objects.get_or_create(
            clinic_id=request.user.clinic_id,
            appointment=appointment,
            defaults={"created_by": request.user},
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

        return Response(
            {
                "transcript": transcript,
                "structured": structured,
                "strict_mode": True,
                "needs_review": needs_review,
                "unknown_fields": [k for k, v in structured.items() if v == SUMMARY_UNKNOWN],
            },
            status=200,
        )


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
            Appointment.objects.filter(id=appointment_id, clinic_id=request.user.clinic_id)
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

        safe_filename = _safe_s3_filename(upload.name or "recording.webm")
        job_id = uuid.uuid4()
        input_s3_key = f"visit_recordings/{job_id}/{safe_filename}"

        try:
            _get_recording_s3_client().upload_fileobj(
                upload,
                bucket,
                input_s3_key,
                ExtraArgs={"ContentType": upload.content_type or "application/octet-stream"},
            )
        except Exception as exc:
            return Response({"detail": f"Upload to storage failed: {exc}"}, status=400)

        with transaction.atomic():
            recording = VisitRecording.objects.create(
                clinic_id=request.user.clinic_id,
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
                    response = _get_recording_s3_client().get_object(
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
            _trigger_visit_recording_uploaded(recording.id)
        except Exception:
            # Best-effort only; processing can still be done by command/scheduler.
            pass

        return Response(VisitRecordingUploadResponseSerializer(recording).data, status=201)


class VisitRecordingListView(APIView):
    permission_classes = [IsAuthenticated, HasClinic, IsDoctorOrAdmin]

    def get(self, request, appointment_id: int):
        appointment = Appointment.objects.filter(
            id=appointment_id,
            clinic_id=request.user.clinic_id,
        ).first()
        if not appointment:
            return Response({"detail": "Appointment not found."}, status=404)
        items = VisitRecording.objects.filter(
            appointment_id=appointment.id,
            clinic_id=request.user.clinic_id,
        ).order_by("-created_at")
        return Response(VisitRecordingSerializer(items, many=True).data, status=200)


class VisitRecordingDetailView(APIView):
    permission_classes = [IsAuthenticated, HasClinic, IsDoctorOrAdmin]

    def get(self, request, recording_id: int):
        item = VisitRecording.objects.filter(
            id=recording_id,
            clinic_id=request.user.clinic_id,
        ).first()
        if not item:
            return Response({"detail": "Visit recording not found."}, status=404)
        return Response(VisitRecordingSerializer(item).data, status=200)


class HospitalStayViewSet(viewsets.ModelViewSet):
    """
    CRUD for hospital stays (in-patient hospitalization).
    Doctor/Admin only for create/update.
    """

    permission_classes = [IsAuthenticated, HasClinic, IsDoctorOrAdmin]

    def get_queryset(self):
        user = self.request.user
        return (
            HospitalStay.objects.filter(clinic_id=user.clinic_id)
            .select_related("patient", "attending_vet", "admission_appointment")
            .order_by("-admitted_at")
        )

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return HospitalStayReadSerializer
        return HospitalStayWriteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            HospitalStayReadSerializer(serializer.instance).data,
            status=201,
        )

    def perform_create(self, serializer):
        serializer.save(clinic_id=self.request.user.clinic_id, status="admitted")

    def _build_discharge_summary_draft(self, stay: HospitalStay) -> dict:
        latest_note = (
            HospitalStayNote.objects.filter(
                clinic_id=self.request.user.clinic_id,
                hospital_stay=stay,
            )
            .order_by("-created_at", "-id")
            .first()
        )
        completed_tasks = HospitalStayTask.objects.filter(
            clinic_id=self.request.user.clinic_id,
            hospital_stay=stay,
            status=HospitalStayTask.Status.COMPLETED,
        ).order_by("-updated_at", "-id")[:5]
        active_medications = HospitalMedicationOrder.objects.filter(
            clinic_id=self.request.user.clinic_id,
            hospital_stay=stay,
            is_active=True,
        ).order_by("-created_at", "-id")

        meds_for_discharge = []
        for medication in active_medications:
            meds_for_discharge.append(
                {
                    "medication_name": medication.medication_name,
                    "dose": str(medication.dose),
                    "dose_unit": medication.dose_unit,
                    "route": medication.route,
                    "frequency_hours": medication.frequency_hours,
                    "instructions": medication.instructions,
                }
            )

        course_lines = []
        if latest_note and latest_note.note:
            course_lines.append(f"Latest round note: {latest_note.note}")
        if completed_tasks:
            course_lines.append(
                "Completed tasks: "
                + "; ".join([task.title for task in completed_tasks if task.title])
            )
        course_text = "\n".join(course_lines).strip()

        return {
            "diagnosis": "",
            "hospitalization_course": course_text,
            "procedures": "",
            "medications_on_discharge": meds_for_discharge,
            "home_care_instructions": "",
            "warning_signs": "",
            "follow_up_date": None,
            "finalized_at": None,
            "source": "draft",
        }

    def _compute_discharge_safety_checks(self, stay: HospitalStay) -> dict:
        summary = HospitalDischargeSummary.objects.filter(
            clinic_id=self.request.user.clinic_id,
            hospital_stay=stay,
        ).first()
        blocking_reasons = []
        warnings = []

        if not summary:
            blocking_reasons.append(
                {
                    "code": "discharge_summary_missing",
                    "detail": "Create and save discharge summary before discharge.",
                }
            )
        else:
            if not (summary.home_care_instructions or "").strip():
                blocking_reasons.append(
                    {
                        "code": "home_care_instructions_missing",
                        "detail": "Home care instructions are required before discharge.",
                    }
                )
            if not (summary.warning_signs or "").strip():
                blocking_reasons.append(
                    {
                        "code": "warning_signs_missing",
                        "detail": "Warning signs are required before discharge.",
                    }
                )
            if summary.finalized_at is None:
                warnings.append(
                    {
                        "code": "discharge_summary_not_finalized",
                        "detail": "Discharge summary is not finalized yet.",
                    }
                )

        unresolved_high_priority_tasks = HospitalStayTask.objects.filter(
            clinic_id=self.request.user.clinic_id,
            hospital_stay=stay,
            priority=HospitalStayTask.Priority.HIGH,
        ).exclude(status=HospitalStayTask.Status.COMPLETED)
        if unresolved_high_priority_tasks.exists():
            blocking_reasons.append(
                {
                    "code": "high_priority_tasks_open",
                    "detail": "All high-priority tasks must be completed before discharge.",
                    "count": unresolved_high_priority_tasks.count(),
                }
            )

        overdue_count = 0
        now = timezone.now()
        active_orders = HospitalMedicationOrder.objects.filter(
            clinic_id=self.request.user.clinic_id,
            hospital_stay=stay,
            is_active=True,
        )
        for order in active_orders:
            if order.ends_at and order.ends_at < now:
                continue
            last_given = (
                HospitalMedicationAdministration.objects.filter(
                    clinic_id=self.request.user.clinic_id,
                    medication_order=order,
                    status=HospitalMedicationAdministration.Status.GIVEN,
                    administered_at__isnull=False,
                )
                .order_by("-administered_at", "-id")
                .first()
            )
            next_due_at = (
                order.starts_at
                if not last_given
                else (last_given.administered_at + timedelta(hours=int(order.frequency_hours or 0)))
            )
            if next_due_at < now:
                overdue_count += 1
        if overdue_count:
            warnings.append(
                {
                    "code": "overdue_medications",
                    "detail": "There are overdue medication administrations.",
                    "count": overdue_count,
                }
            )

        return {
            "ready_to_discharge": len(blocking_reasons) == 0,
            "blocking_reasons": blocking_reasons,
            "warnings": warnings,
        }

    @action(detail=True, methods=["post"], url_path="discharge")
    def discharge(self, request, pk=None):
        """Discharge the patient from hospital."""
        from django.utils import timezone

        stay = self.get_object()
        if stay.status != "admitted":
            return Response(
                {"detail": "Stay is already discharged."},
                status=400,
            )
        require_safety = bool(getattr(settings, "REQUIRE_DISCHARGE_SAFETY_FOR_DISCHARGE", False))
        if require_safety:
            safety = self._compute_discharge_safety_checks(stay)
            if not safety["ready_to_discharge"]:
                return Response(
                    {
                        "detail": "Discharge blocked by safety checks.",
                        "code": "discharge_safety_failed",
                        "blocking_reasons": safety["blocking_reasons"],
                        "warnings": safety["warnings"],
                    },
                    status=400,
                )
        stay.status = "discharged"
        stay.discharged_at = timezone.now()
        stay.discharge_notes = request.data.get("discharge_notes", "")
        stay.save(update_fields=["status", "discharged_at", "discharge_notes", "updated_at"])
        return Response(HospitalStayReadSerializer(stay).data)

    @action(detail=True, methods=["get"], url_path="discharge-safety-checks")
    def discharge_safety_checks(self, request, pk=None):
        stay = self.get_object()
        safety = self._compute_discharge_safety_checks(stay)
        return Response(
            {
                "hospital_stay_id": stay.id,
                **safety,
            },
            status=200,
        )

    @action(detail=True, methods=["get", "put"], url_path="discharge-summary")
    def discharge_summary(self, request, pk=None):
        stay = self.get_object()
        summary = HospitalDischargeSummary.objects.filter(
            clinic_id=request.user.clinic_id,
            hospital_stay=stay,
        ).first()

        if request.method == "GET":
            if summary:
                data = HospitalDischargeSummaryReadSerializer(summary).data
                data["source"] = "saved"
                return Response(data, status=200)
            return Response(self._build_discharge_summary_draft(stay), status=200)

        serializer = HospitalDischargeSummaryWriteSerializer(
            summary,
            data=request.data,
            partial=bool(summary),
        )
        serializer.is_valid(raise_exception=True)
        if summary:
            summary = serializer.save()
        else:
            summary = serializer.save(
                clinic_id=request.user.clinic_id,
                hospital_stay=stay,
                generated_by=request.user,
            )
        data = HospitalDischargeSummaryReadSerializer(summary).data
        data["source"] = "saved"
        return Response(data, status=200)

    @action(detail=True, methods=["post"], url_path="discharge-summary/finalize")
    def finalize_discharge_summary(self, request, pk=None):
        stay = self.get_object()
        summary = HospitalDischargeSummary.objects.filter(
            clinic_id=request.user.clinic_id,
            hospital_stay=stay,
        ).first()
        if not summary:
            return Response(
                {"detail": "Create discharge summary before finalizing."},
                status=400,
            )
        if stay.status != HospitalStay.Status.DISCHARGED:
            return Response(
                {"detail": "Patient must be discharged before finalizing summary."},
                status=400,
            )
        summary.finalized_at = timezone.now()
        summary.generated_by = request.user
        summary.save(update_fields=["finalized_at", "generated_by", "updated_at"])
        data = HospitalDischargeSummaryReadSerializer(summary).data
        data["source"] = "saved"
        return Response(data, status=200)

    @action(detail=True, methods=["get"], url_path="discharge-summary/pdf")
    def discharge_summary_pdf(self, request, pk=None):
        stay = self.get_object()
        summary = HospitalDischargeSummary.objects.filter(
            clinic_id=request.user.clinic_id,
            hospital_stay=stay,
        ).first()
        if not summary:
            return Response(
                {"detail": "Discharge summary not found."},
                status=404,
            )

        summary_data = HospitalDischargeSummaryReadSerializer(summary).data
        pdf_bytes = render_discharge_summary_pdf_bytes(summary_data)
        filename = f"discharge_summary_stay_{stay.id}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=["get", "post"], url_path="notes")
    def notes(self, request, pk=None):
        stay = self.get_object()
        if request.method == "GET":
            items = HospitalStayNote.objects.filter(
                clinic_id=request.user.clinic_id,
                hospital_stay=stay,
            ).order_by("-created_at", "-id")
            return Response(HospitalStayNoteReadSerializer(items, many=True).data, status=200)

        serializer = HospitalStayNoteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.save(
            clinic_id=request.user.clinic_id,
            hospital_stay=stay,
            created_by=request.user,
        )
        return Response(HospitalStayNoteReadSerializer(note).data, status=201)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"notes/(?P<note_id>[^/.]+)",
    )
    def note_detail(self, request, pk=None, note_id=None):
        stay = self.get_object()
        note = HospitalStayNote.objects.filter(
            id=note_id,
            clinic_id=request.user.clinic_id,
            hospital_stay=stay,
        ).first()
        if not note:
            return Response({"detail": "Note not found."}, status=404)

        if request.method == "DELETE":
            note.delete()
            return Response(status=204)

        serializer = HospitalStayNoteWriteSerializer(note, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        note = serializer.save()
        return Response(HospitalStayNoteReadSerializer(note).data, status=200)

    @action(detail=True, methods=["get", "post"], url_path="tasks")
    def tasks(self, request, pk=None):
        stay = self.get_object()
        if request.method == "GET":
            items = HospitalStayTask.objects.filter(
                clinic_id=request.user.clinic_id,
                hospital_stay=stay,
            ).order_by("status", "due_at", "id")
            return Response(HospitalStayTaskReadSerializer(items, many=True).data, status=200)

        serializer = HospitalStayTaskWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.save(
            clinic_id=request.user.clinic_id,
            hospital_stay=stay,
            created_by=request.user,
        )
        if task.status == HospitalStayTask.Status.COMPLETED:
            task.completed_at = timezone.now()
            task.completed_by = request.user
            task.save(update_fields=["completed_at", "completed_by", "updated_at"])
        return Response(HospitalStayTaskReadSerializer(task).data, status=201)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"tasks/(?P<task_id>[^/.]+)",
    )
    def task_detail(self, request, pk=None, task_id=None):
        stay = self.get_object()
        task = HospitalStayTask.objects.filter(
            id=task_id,
            clinic_id=request.user.clinic_id,
            hospital_stay=stay,
        ).first()
        if not task:
            return Response({"detail": "Task not found."}, status=404)

        if request.method == "DELETE":
            task.delete()
            return Response(status=204)

        previous_status = task.status
        serializer = HospitalStayTaskWriteSerializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        task = serializer.save()
        if (
            previous_status != HospitalStayTask.Status.COMPLETED
            and task.status == HospitalStayTask.Status.COMPLETED
        ):
            task.completed_at = timezone.now()
            task.completed_by = request.user
            task.save(update_fields=["completed_at", "completed_by", "updated_at"])
        if (
            previous_status == HospitalStayTask.Status.COMPLETED
            and task.status != HospitalStayTask.Status.COMPLETED
        ):
            task.completed_at = None
            task.completed_by = None
            task.save(update_fields=["completed_at", "completed_by", "updated_at"])
        return Response(HospitalStayTaskReadSerializer(task).data, status=200)

    @action(detail=True, methods=["get", "post"], url_path="medications")
    def medications(self, request, pk=None):
        stay = self.get_object()
        if request.method == "GET":
            items = HospitalMedicationOrder.objects.filter(
                clinic_id=request.user.clinic_id,
                hospital_stay=stay,
            ).order_by("-created_at", "-id")
            return Response(
                HospitalMedicationOrderReadSerializer(items, many=True).data, status=200
            )

        serializer = HospitalMedicationOrderWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        medication = serializer.save(
            clinic_id=request.user.clinic_id,
            hospital_stay=stay,
            created_by=request.user,
        )
        return Response(HospitalMedicationOrderReadSerializer(medication).data, status=201)

    @action(detail=True, methods=["post"], url_path="medications/generate-schedule")
    def generate_medication_schedule(self, request, pk=None):
        """
        Generate pending medication administrations for active medication orders.
        Idempotent: does not create duplicates for the same (order, scheduled_for).
        """
        stay = self.get_object()
        horizon_hours = request.query_params.get("horizon_hours", "24")
        past_hours = request.query_params.get("past_hours", "12")
        try:
            horizon_hours_int = int(horizon_hours)
            past_hours_int = int(past_hours)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid horizon_hours or past_hours."}, status=400)
        if horizon_hours_int <= 0 or horizon_hours_int > 24 * 14:
            return Response({"detail": "horizon_hours must be between 1 and 336."}, status=400)
        if past_hours_int < 0 or past_hours_int > 24 * 14:
            return Response({"detail": "past_hours must be between 0 and 336."}, status=400)

        now = timezone.now()
        window_start = now - timedelta(hours=past_hours_int)
        window_end = now + timedelta(hours=horizon_hours_int)

        orders = HospitalMedicationOrder.objects.filter(
            clinic_id=request.user.clinic_id,
            hospital_stay=stay,
            is_active=True,
        ).order_by("-created_at", "-id")

        created = 0
        skipped_existing = 0

        with transaction.atomic():
            for order in orders:
                if order.ends_at and order.ends_at < window_start:
                    continue
                if order.starts_at and order.starts_at > window_end:
                    continue

                freq = int(order.frequency_hours or 0)
                if freq <= 0:
                    continue

                start = max(order.starts_at, window_start)
                # Align to the order starts_at cadence
                delta_seconds = (start - order.starts_at).total_seconds()
                steps = int(delta_seconds // (freq * 3600))
                candidate = order.starts_at + timedelta(hours=freq * steps)
                while candidate < start:
                    candidate = candidate + timedelta(hours=freq)

                existing_times = set(
                    HospitalMedicationAdministration.objects.filter(
                        clinic_id=request.user.clinic_id,
                        medication_order=order,
                        scheduled_for__gte=window_start,
                        scheduled_for__lte=window_end,
                    ).values_list("scheduled_for", flat=True)
                )

                to_create = []
                while candidate <= window_end:
                    if order.ends_at and candidate > order.ends_at:
                        break
                    if candidate in existing_times:
                        skipped_existing += 1
                    else:
                        to_create.append(
                            HospitalMedicationAdministration(
                                clinic_id=request.user.clinic_id,
                                medication_order=order,
                                scheduled_for=candidate,
                                status=HospitalMedicationAdministration.Status.PENDING,
                            )
                        )
                        existing_times.add(candidate)
                    candidate = candidate + timedelta(hours=freq)

                if to_create:
                    HospitalMedicationAdministration.objects.bulk_create(to_create)
                    created += len(to_create)

        return Response(
            {
                "hospital_stay_id": stay.id,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "created": created,
                "skipped_existing": skipped_existing,
            },
            status=200,
        )

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"medications/(?P<medication_id>[^/.]+)",
    )
    def medication_detail(self, request, pk=None, medication_id=None):
        stay = self.get_object()
        medication = HospitalMedicationOrder.objects.filter(
            id=medication_id,
            clinic_id=request.user.clinic_id,
            hospital_stay=stay,
        ).first()
        if not medication:
            return Response({"detail": "Medication order not found."}, status=404)

        if request.method == "DELETE":
            medication.delete()
            return Response(status=204)

        serializer = HospitalMedicationOrderWriteSerializer(
            medication, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        medication = serializer.save()
        return Response(HospitalMedicationOrderReadSerializer(medication).data, status=200)

    @action(
        detail=True,
        methods=["get", "post"],
        url_path=r"medications/(?P<medication_id>[^/.]+)/administrations",
    )
    def medication_administrations(self, request, pk=None, medication_id=None):
        stay = self.get_object()
        medication = HospitalMedicationOrder.objects.filter(
            id=medication_id,
            clinic_id=request.user.clinic_id,
            hospital_stay=stay,
        ).first()
        if not medication:
            return Response({"detail": "Medication order not found."}, status=404)

        if request.method == "GET":
            items = HospitalMedicationAdministration.objects.filter(
                clinic_id=request.user.clinic_id,
                medication_order=medication,
            ).order_by("-scheduled_for", "-created_at", "-id")
            return Response(
                HospitalMedicationAdministrationReadSerializer(items, many=True).data,
                status=200,
            )

        serializer = HospitalMedicationAdministrationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        administration = serializer.save(
            clinic_id=request.user.clinic_id,
            medication_order=medication,
        )
        if administration.status == HospitalMedicationAdministration.Status.GIVEN:
            if administration.administered_at is None:
                administration.administered_at = timezone.now()
            administration.administered_by = request.user
            administration.save(update_fields=["administered_at", "administered_by", "updated_at"])
        return Response(
            HospitalMedicationAdministrationReadSerializer(administration).data,
            status=201,
        )

    @action(
        detail=True,
        methods=["patch"],
        url_path=r"medications/(?P<medication_id>[^/.]+)/administrations/(?P<administration_id>[^/.]+)",
    )
    def medication_administration_detail(
        self, request, pk=None, medication_id=None, administration_id=None
    ):
        stay = self.get_object()
        medication = HospitalMedicationOrder.objects.filter(
            id=medication_id,
            clinic_id=request.user.clinic_id,
            hospital_stay=stay,
        ).first()
        if not medication:
            return Response({"detail": "Medication order not found."}, status=404)

        administration = HospitalMedicationAdministration.objects.filter(
            id=administration_id,
            clinic_id=request.user.clinic_id,
            medication_order=medication,
        ).first()
        if not administration:
            return Response({"detail": "Medication administration not found."}, status=404)

        previous_status = administration.status
        serializer = HospitalMedicationAdministrationWriteSerializer(
            administration, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        administration = serializer.save()
        if administration.status == HospitalMedicationAdministration.Status.GIVEN:
            if administration.administered_at is None:
                administration.administered_at = timezone.now()
            if previous_status != HospitalMedicationAdministration.Status.GIVEN:
                administration.administered_by = request.user
            administration.save(update_fields=["administered_at", "administered_by", "updated_at"])
        if (
            previous_status == HospitalMedicationAdministration.Status.GIVEN
            and administration.status != HospitalMedicationAdministration.Status.GIVEN
        ):
            administration.administered_at = None
            administration.administered_by = None
            administration.save(update_fields=["administered_at", "administered_by", "updated_at"])
        return Response(
            HospitalMedicationAdministrationReadSerializer(administration).data, status=200
        )

    @action(detail=True, methods=["get"], url_path="medications-due")
    def medications_due(self, request, pk=None):
        stay = self.get_object()

        window = request.query_params.get("window_minutes", "30")
        include_overdue = request.query_params.get("include_overdue", "1")
        try:
            window_minutes = int(window)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid window_minutes."}, status=400)
        if window_minutes < 0 or window_minutes > 24 * 60:
            return Response(
                {"detail": "window_minutes must be between 0 and 1440."},
                status=400,
            )

        include_overdue_bool = str(include_overdue).lower() not in ("0", "false", "no")
        now = timezone.now()
        horizon = now + timedelta(minutes=window_minutes)

        orders = HospitalMedicationOrder.objects.filter(
            clinic_id=request.user.clinic_id,
            hospital_stay=stay,
            is_active=True,
        ).order_by("-created_at", "-id")

        due_items = []
        for order in orders:
            if order.ends_at and order.ends_at < now:
                continue
            if order.starts_at and order.starts_at > horizon:
                continue

            last_given = (
                HospitalMedicationAdministration.objects.filter(
                    clinic_id=request.user.clinic_id,
                    medication_order=order,
                    status=HospitalMedicationAdministration.Status.GIVEN,
                    administered_at__isnull=False,
                )
                .order_by("-administered_at", "-id")
                .first()
            )

            if last_given is None:
                next_due_at = order.starts_at
            else:
                next_due_at = last_given.administered_at + timedelta(
                    hours=int(order.frequency_hours or 0)
                )

            overdue = next_due_at < now
            if overdue and not include_overdue_bool:
                continue
            if not overdue and next_due_at > horizon:
                continue

            due_items.append(
                {
                    "medication_order": HospitalMedicationOrderReadSerializer(order).data,
                    "last_given_at": (
                        last_given.administered_at.isoformat()
                        if last_given and last_given.administered_at
                        else None
                    ),
                    "next_due_at": next_due_at.isoformat(),
                    "is_overdue": overdue,
                    "overdue_minutes": (
                        int((now - next_due_at).total_seconds() // 60) if overdue else 0
                    ),
                }
            )

        due_items.sort(key=lambda x: x["next_due_at"])
        return Response(
            {
                "hospital_stay_id": stay.id,
                "now": now.isoformat(),
                "window_minutes": window_minutes,
                "include_overdue": include_overdue_bool,
                "items": due_items,
            },
            status=200,
        )


class RoomViewSet(viewsets.ReadOnlyModelViewSet):
    """List rooms for the user's clinic (for dropdowns and calendar). Manage rooms in Django admin."""

    permission_classes = [IsAuthenticated, HasClinic]
    serializer_class = RoomSerializer

    def get_queryset(self):
        return Room.objects.filter(clinic_id=self.request.user.clinic_id).order_by(
            "display_order", "name"
        )


class AvailabilityView(APIView):
    """
    Read-only endpoint returning available time slots for a given date.
    Optional vet-specific availability.
    """

    permission_classes = [IsAuthenticated, HasClinic]

    def get(self, request):
        user = request.user

        # ---- date validation (robust, no 500s) ----
        date_str = request.query_params.get("date")
        if not date_str:
            return Response(
                {"detail": "Missing required query param: date=YYYY-MM-DD"},
                status=400,
            )

        try:
            parsed_day: date_type | None = parse_date(date_str)
        except ValueError:
            parsed_day = None

        if parsed_day is None:
            return Response(
                {"detail": "Invalid date. Use YYYY-MM-DD (e.g., 2025-12-23)."},
                status=400,
            )

        # ---- optional params ----
        vet = request.query_params.get("vet")
        vet_id = int(vet) if vet else None

        room = request.query_params.get("room")
        room_id = int(room) if room else None

        slot = request.query_params.get("slot")
        slot_minutes = int(slot) if slot else None

        # ---- compute availability ----
        data = compute_availability(
            clinic_id=user.clinic_id,
            date_str=date_str,
            vet_id=vet_id,
            room_id=room_id,
            slot_minutes=slot_minutes,
        )

        work_bounds = data.get("work_bounds")

        def dump_interval(interval):
            return {
                "start": interval.start.isoformat(),
                "end": interval.end.isoformat(),
            }

        return Response(
            {
                "date": date_str,
                "timezone": data["timezone"],
                "clinic_id": user.clinic_id,
                "vet_id": vet_id,
                "room_id": room_id,
                "slot_minutes": data["slot_minutes"],
                "closed_reason": data.get("closed_reason"),
                "workday": dump_interval(work_bounds) if work_bounds else None,
                "work_intervals": [dump_interval(i) for i in data["work_intervals"]],
                "busy": [dump_interval(i) for i in data["busy_merged"]],
                "free": [dump_interval(i) for i in data["free_slots"]],
            }
        )


class AvailabilityRoomsView(APIView):
    """
    GET /availability/rooms/?date=YYYY-MM-DD
    Returns availability per room for the given date (for calendar room view).
    """

    permission_classes = [IsAuthenticated, HasClinic]

    def get(self, request):
        user = request.user
        date_str = request.query_params.get("date")
        if not date_str:
            return Response(
                {"detail": "Missing required query param: date=YYYY-MM-DD"},
                status=400,
            )
        try:
            parse_date(date_str)
        except ValueError:
            return Response(
                {"detail": "Invalid date. Use YYYY-MM-DD."},
                status=400,
            )

        rooms = Room.objects.filter(clinic_id=user.clinic_id).order_by("display_order", "name")
        slot_minutes = 30
        result = []

        def dump_interval(interval):
            return {
                "start": interval.start.isoformat(),
                "end": interval.end.isoformat(),
            }

        for room in rooms:
            data = compute_availability(
                clinic_id=user.clinic_id,
                date_str=date_str,
                vet_id=None,
                room_id=room.id,
                slot_minutes=slot_minutes,
            )
            result.append(
                {
                    "id": room.id,
                    "name": room.name,
                    "busy": [dump_interval(i) for i in data["busy_merged"]],
                    "free": [dump_interval(i) for i in data["free_slots"]],
                    "workday": (
                        dump_interval(data["work_bounds"]) if data.get("work_bounds") else None
                    ),
                    "closed_reason": data.get("closed_reason"),
                }
            )

        return Response({"date": date_str, "rooms": result})


class WaitingQueueViewSet(viewsets.ModelViewSet):
    """
    Walk-in patient queue. Receptionist/doctor adds patients; doctor calls them.
    List returns only active entries (waiting or in_progress).
    """

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        return (
            WaitingQueueEntry.objects.filter(
                clinic_id=self.request.user.clinic_id,
                status__in=[
                    WaitingQueueEntry.Status.WAITING,
                    WaitingQueueEntry.Status.IN_PROGRESS,
                ],
            )
            .select_related("patient", "patient__owner", "called_by")
            .order_by("position", "arrived_at")
        )

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return WaitingQueueEntryReadSerializer
        return WaitingQueueEntryWriteSerializer

    def perform_create(self, serializer):
        clinic_id = self.request.user.clinic_id
        max_pos = (
            WaitingQueueEntry.objects.filter(
                clinic_id=clinic_id,
                status__in=[
                    WaitingQueueEntry.Status.WAITING,
                    WaitingQueueEntry.Status.IN_PROGRESS,
                ],
            ).aggregate(m=models.Max("position"))["m"]
            or 0
        )
        serializer.save(clinic_id=clinic_id, position=max_pos + 1)

    @action(detail=True, methods=["post"], url_path="move-up")
    def move_up(self, request, pk=None):
        entry = self.get_object()
        above = (
            WaitingQueueEntry.objects.filter(
                clinic_id=entry.clinic_id,
                status__in=[
                    WaitingQueueEntry.Status.WAITING,
                    WaitingQueueEntry.Status.IN_PROGRESS,
                ],
                position__lt=entry.position,
            )
            .order_by("-position")
            .first()
        )
        if above:
            entry.position, above.position = above.position, entry.position
            entry.save(update_fields=["position"])
            above.save(update_fields=["position"])
        return Response(WaitingQueueEntryReadSerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="move-down")
    def move_down(self, request, pk=None):
        entry = self.get_object()
        below = (
            WaitingQueueEntry.objects.filter(
                clinic_id=entry.clinic_id,
                status__in=[
                    WaitingQueueEntry.Status.WAITING,
                    WaitingQueueEntry.Status.IN_PROGRESS,
                ],
                position__gt=entry.position,
            )
            .order_by("position")
            .first()
        )
        if below:
            entry.position, below.position = below.position, entry.position
            entry.save(update_fields=["position"])
            below.save(update_fields=["position"])
        return Response(WaitingQueueEntryReadSerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="call")
    def call(self, request, pk=None):
        if not IsDoctorOrAdmin().has_permission(request, self):
            raise PermissionDenied("Only doctors and clinic admins can call a patient.")
        entry = self.get_object()
        if entry.status != WaitingQueueEntry.Status.WAITING:
            return Response({"detail": "Entry is not in waiting status."}, status=400)

        already_active = WaitingQueueEntry.objects.filter(
            clinic_id=entry.clinic_id,
            called_by=request.user,
            status=WaitingQueueEntry.Status.IN_PROGRESS,
        ).exists()
        if already_active:
            return Response(
                {
                    "detail": "You already have a patient in progress. Close the current visit first."
                },
                status=409,
            )

        entry.status = WaitingQueueEntry.Status.IN_PROGRESS
        entry.called_by = request.user
        entry.save(update_fields=["status", "called_by"])

        return Response(WaitingQueueEntryReadSerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="requeue")
    def requeue(self, request, pk=None):
        if not IsDoctorOrAdmin().has_permission(request, self):
            raise PermissionDenied("Only doctors and clinic admins can requeue a patient.")
        entry = self.get_object()
        if entry.status != WaitingQueueEntry.Status.IN_PROGRESS:
            return Response({"detail": "Entry is not in progress."}, status=400)
        entry.status = WaitingQueueEntry.Status.WAITING
        entry.called_by = None
        entry.save(update_fields=["status", "called_by"])
        return Response(WaitingQueueEntryReadSerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="done")
    def done(self, request, pk=None):
        if not IsDoctorOrAdmin().has_permission(request, self):
            raise PermissionDenied("Only doctors and clinic admins can mark a visit as done.")
        entry = self.get_object()
        entry.status = WaitingQueueEntry.Status.DONE
        entry.save(update_fields=["status"])
        return Response(status=204)
