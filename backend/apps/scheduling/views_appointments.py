from __future__ import annotations

import csv
from datetime import timedelta
from io import StringIO

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsDoctorOrAdmin, IsStaffOrVet
from apps.audit.services import log_audit_event
from apps.medical.models import ClinicalExam, ClinicalExamTemplate, ProcedureSupplyTemplate
from apps.medical.serializers import ClinicalExamReadSerializer, ClinicalExamWriteSerializer
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.scheduling.serializers import AppointmentReadSerializer, AppointmentWriteSerializer
from apps.tenancy.access import accessible_clinic_ids, clinic_instance_for_mutation


class AppointmentViewSet(viewsets.ModelViewSet):
    """
    CRUD for appointments within the user's clinic.
    Supports filtering by date, vet, patient, status, visit_type, and booked_via_portal.
    """

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        user = self.request.user

        qs = (
            Appointment.objects.filter(clinic_id__in=accessible_clinic_ids(user))
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

        bvp = (self.request.query_params.get("booked_via_portal") or "").strip().lower()
        if bvp in ("1", "true", "yes"):
            qs = qs.filter(booked_via_portal=True)
        elif bvp in ("0", "false", "no"):
            qs = qs.filter(booked_via_portal=False)

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
        clinic = clinic_instance_for_mutation(self.request.user, self.request)
        appointment = serializer.save(clinic=clinic)
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
        clinic = clinic_instance_for_mutation(
            self.request.user,
            self.request,
            instance_clinic_id=serializer.instance.clinic_id,
        )
        appointment = serializer.save(clinic=clinic)
        if appointment.status == Appointment.Status.CANCELLED and appointment.cancelled_at is None:
            appointment.cancelled_at = timezone.now()
            appointment.save(update_fields=["cancelled_at", "updated_at"])
        if old_status and old_status != appointment.status:
            log_audit_event(
                clinic_id=appointment.clinic_id,
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
            clinic_id__in=accessible_clinic_ids(request.user),
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
                clinic_id__in=accessible_clinic_ids(user),
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
                clinic_id=appt.clinic_id,
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

    @action(detail=True, methods=["post"], url_path="exam/apply-template")
    def apply_exam_template(self, request, pk=None):
        """
        POST /api/appointments/<id>/exam/apply-template/
        Body: {"template_id": <id>, "force": false}
        """
        if not IsDoctorOrAdmin().has_permission(request, self):
            raise PermissionDenied("Only doctors and clinic admins can apply exam templates.")

        appt = self.get_object()
        template_id = request.data.get("template_id")
        force = bool(request.data.get("force", False))
        if not template_id:
            return Response({"detail": "template_id is required."}, status=400)

        template = ClinicalExamTemplate.objects.filter(
            id=template_id,
            clinic_id__in=accessible_clinic_ids(request.user),
            is_active=True,
        ).first()
        if not template:
            return Response({"detail": "Template not found."}, status=404)

        exam = (
            ClinicalExam.objects.filter(
                appointment_id=appt.id,
                clinic_id__in=accessible_clinic_ids(request.user),
            )
            .order_by("id")
            .first()
        )
        if not exam:
            exam = ClinicalExam.objects.create(
                clinic_id=appt.clinic_id,
                appointment=appt,
                created_by=request.user,
            )

        writable_fields = [
            "initial_notes",
            "clinical_examination",
            "temperature_c",
            "heart_rate_bpm",
            "respiratory_rate_rpm",
            "weight_kg",
            "additional_notes",
            "owner_instructions",
            "initial_diagnosis",
        ]
        defaults = template.defaults or {}
        payload = {field: getattr(exam, field) for field in writable_fields}
        applied_fields = []
        for field in writable_fields:
            if field not in defaults:
                continue
            current = payload.get(field)
            if force or current in (None, ""):
                payload[field] = defaults[field]
                applied_fields.append(field)

        before_values = {field: getattr(exam, field) for field in applied_fields}
        serializer = ClinicalExamWriteSerializer(exam, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)
        exam = serializer.save()
        after_values = {field: getattr(exam, field) for field in applied_fields}
        log_audit_event(
            clinic_id=appt.clinic_id,
            actor=request.user,
            action="clinical_exam_template_applied",
            entity_type="appointment",
            entity_id=appt.id,
            before=before_values,
            after=after_values,
            metadata={
                "clinical_exam_id": exam.id,
                "template_id": template.id,
                "template_name": template.name,
                "applied_fields": applied_fields,
                "force": force,
            },
        )
        data = ClinicalExamReadSerializer(exam).data
        data["template_meta"] = {
            "template_id": template.id,
            "template_name": template.name,
            "applied_fields": applied_fields,
            "force": force,
        }
        return Response(data, status=200)

    @action(detail=True, methods=["post"], url_path="procedure-supply-template-preview")
    def procedure_supply_template_preview(self, request, pk=None):
        """
        POST /api/appointments/<id>/procedure-supply-template-preview/
        Body: {"template_id": <int>} — suggested invoice line payloads only; no invoice or stock movement.
        """
        template_id = request.data.get("template_id")
        if not template_id:
            return Response({"detail": "template_id is required."}, status=400)

        self.get_object()
        template = (
            ProcedureSupplyTemplate.objects.filter(
                id=template_id,
                clinic_id__in=accessible_clinic_ids(request.user),
                is_active=True,
            )
            .prefetch_related("lines__inventory_item")
            .first()
        )
        if not template:
            return Response({"detail": "Template not found."}, status=404)

        suggested_lines = []
        for line in template.lines.all():
            item = line.inventory_item
            suggested_lines.append(
                {
                    "inventory_item_id": item.id,
                    "inventory_item_name": item.name,
                    "sku": item.sku,
                    "unit": item.unit,
                    "suggested_quantity": str(line.suggested_quantity),
                    "default_unit_price": (
                        str(line.default_unit_price)
                        if line.default_unit_price is not None
                        else None
                    ),
                    "vat_rate": line.vat_rate,
                    "description": item.name,
                    "is_optional": line.is_optional,
                    "stock_on_hand": item.stock_on_hand,
                    "inventory_item_is_active": item.is_active,
                    "notes": line.notes,
                }
            )

        return Response(
            {
                "template_id": template.id,
                "template_name": template.name,
                "suggested_lines": suggested_lines,
            },
            status=200,
        )

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
                clinic_id__in=accessible_clinic_ids(user),
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
                    clinic_id__in=accessible_clinic_ids(request.user),
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
            clinic_id=appt.clinic_id,
            actor=request.user,
            action="visit_closed",
            entity_type="appointment",
            entity_id=appt.id,
            before={"status": old_status},
            after={"status": appt.status},
        )

        return Response(status=204)
