from __future__ import annotations

import csv
from datetime import timedelta
from io import StringIO

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Max, OuterRef, Q, Subquery
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsDoctorOrAdmin, IsStaffOrVet
from apps.audit.services import log_audit_event
from apps.scheduling.models import (
    HospitalDischargeSummary,
    HospitalMedicationAdministration,
    HospitalMedicationOrder,
    HospitalStay,
    HospitalStayNote,
    HospitalStayTask,
)
from apps.scheduling.serializers import (
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
)
from apps.scheduling.services.discharge_pdf import render_discharge_summary_pdf_bytes
from apps.tenancy.access import (
    accessible_clinic_ids,
    clinic_id_for_mutation,
)


class HospitalStayViewSet(viewsets.ModelViewSet):
    """
    CRUD for hospital stays (in-patient hospitalization).
    Doctor/Admin only for create/update.
    """

    permission_classes = [IsAuthenticated, HasClinic, IsDoctorOrAdmin]

    def get_permissions(self):
        # Staff dashboard should be accessible to broader clinic staff.
        if self.action in ("nursing_dashboard", "shift_handover_report"):
            return [IsAuthenticated(), HasClinic(), IsStaffOrVet()]
        return [permission() for permission in self.permission_classes]

    def get_queryset(self):
        user = self.request.user
        return (
            HospitalStay.objects.filter(clinic_id__in=accessible_clinic_ids(user))
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
        cid = clinic_id_for_mutation(
            self.request.user, request=self.request, instance_clinic_id=None
        )
        serializer.save(clinic_id=cid, status="admitted")

    @action(detail=False, methods=["get"], url_path="nursing-dashboard")
    def nursing_dashboard(self, request):
        """
        Clinic-wide dashboard for active hospital stays (admitted).
        Intended for nursing/front-desk workflow triage.
        """
        window = request.query_params.get("window_minutes", "30")
        limit = request.query_params.get("limit", "50")
        try:
            window_minutes = int(window)
            limit_int = int(limit)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid window_minutes or limit."}, status=400)
        if window_minutes < 0 or window_minutes > 24 * 60:
            return Response(
                {"detail": "window_minutes must be between 0 and 1440."},
                status=400,
            )
        if limit_int < 1 or limit_int > 200:
            return Response({"detail": "limit must be between 1 and 200."}, status=400)

        now = timezone.now()
        horizon = now + timedelta(minutes=window_minutes)

        latest_note_qs = HospitalStayNote.objects.filter(
            clinic_id__in=accessible_clinic_ids(request.user),
            hospital_stay_id=OuterRef("pk"),
        ).order_by("-created_at", "-id")

        stays = (
            HospitalStay.objects.filter(
                clinic_id__in=accessible_clinic_ids(request.user),
                status=HospitalStay.Status.ADMITTED,
            )
            .select_related("patient", "attending_vet")
            .annotate(
                last_round_note=Subquery(latest_note_qs.values("note")[:1]),
                last_round_at=Subquery(latest_note_qs.values("created_at")[:1]),
                open_high_priority_tasks=Count(
                    "tasks",
                    filter=Q(tasks__priority=HospitalStayTask.Priority.HIGH)
                    & ~Q(tasks__status=HospitalStayTask.Status.COMPLETED),
                    distinct=True,
                ),
            )
            .order_by("-admitted_at")[:limit_int]
        )

        stay_ids = [s.id for s in stays]
        meds_overdue_by_stay: dict[int, int] = {sid: 0 for sid in stay_ids}
        meds_due_soon_by_stay: dict[int, int] = {sid: 0 for sid in stay_ids}

        if stay_ids:
            orders = (
                HospitalMedicationOrder.objects.filter(
                    clinic_id__in=accessible_clinic_ids(request.user),
                    hospital_stay_id__in=stay_ids,
                    is_active=True,
                )
                .annotate(
                    last_given_at=Max(
                        "administrations__administered_at",
                        filter=Q(
                            administrations__status=HospitalMedicationAdministration.Status.GIVEN
                        ),
                    )
                )
                .only(
                    "id",
                    "hospital_stay_id",
                    "frequency_hours",
                    "starts_at",
                    "ends_at",
                    "is_active",
                )
            )

            for order in orders:
                if order.ends_at and order.ends_at < now:
                    continue
                freq = int(order.frequency_hours or 0)
                if freq <= 0:
                    continue
                next_due_at = (
                    order.starts_at
                    if not order.last_given_at
                    else (order.last_given_at + timedelta(hours=freq))
                )
                if next_due_at < now:
                    meds_overdue_by_stay[order.hospital_stay_id] = (
                        meds_overdue_by_stay.get(order.hospital_stay_id, 0) + 1
                    )
                elif next_due_at <= horizon:
                    meds_due_soon_by_stay[order.hospital_stay_id] = (
                        meds_due_soon_by_stay.get(order.hospital_stay_id, 0) + 1
                    )

        items = []
        for stay in stays:
            data = HospitalStayReadSerializer(stay).data
            data["last_round_note"] = getattr(stay, "last_round_note", None)
            last_round_at = getattr(stay, "last_round_at", None)
            data["last_round_at"] = last_round_at.isoformat() if last_round_at else None
            data["open_high_priority_tasks"] = int(getattr(stay, "open_high_priority_tasks", 0))
            data["meds_overdue"] = meds_overdue_by_stay.get(stay.id, 0)
            data["meds_due_soon"] = meds_due_soon_by_stay.get(stay.id, 0)
            items.append(data)

        # Sort by urgency: overdue meds, then due soon, then open high tasks, then most recent admit
        items.sort(
            key=lambda x: (
                -int(x.get("meds_overdue") or 0),
                -int(x.get("meds_due_soon") or 0),
                -int(x.get("open_high_priority_tasks") or 0),
                x.get("admitted_at") or "",
            )
        )

        return Response(
            {
                "now": now.isoformat(),
                "window_minutes": window_minutes,
                "count": len(items),
                "items": items,
            },
            status=200,
        )

    @action(detail=False, methods=["get"], url_path="shift-handover-report")
    def shift_handover_report(self, request):
        """
        Shift handover report for hospitalization operations.
        """
        hours = request.query_params.get("hours", "12")
        try:
            hours_int = int(hours)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid hours."}, status=400)
        if hours_int < 1 or hours_int > 72:
            return Response({"detail": "hours must be between 1 and 72."}, status=400)

        now = timezone.now()
        since = now - timedelta(hours=hours_int)

        admissions_qs = (
            HospitalStay.objects.filter(
                clinic_id__in=accessible_clinic_ids(request.user),
                admitted_at__gte=since,
                admitted_at__lte=now,
            )
            .select_related("patient", "attending_vet")
            .order_by("-admitted_at")
        )
        discharges_qs = (
            HospitalStay.objects.filter(
                clinic_id__in=accessible_clinic_ids(request.user),
                discharged_at__gte=since,
                discharged_at__lte=now,
            )
            .select_related("patient", "attending_vet")
            .order_by("-discharged_at")
        )
        open_high_tasks_qs = (
            HospitalStayTask.objects.filter(
                clinic_id__in=accessible_clinic_ids(request.user),
                priority=HospitalStayTask.Priority.HIGH,
            )
            .exclude(status=HospitalStayTask.Status.COMPLETED)
            .select_related("hospital_stay", "hospital_stay__patient")
            .order_by("due_at", "id")
        )
        latest_notes_qs = (
            HospitalStayNote.objects.filter(
                clinic_id__in=accessible_clinic_ids(request.user),
                created_at__gte=since,
                created_at__lte=now,
            )
            .select_related("hospital_stay", "hospital_stay__patient", "created_by")
            .order_by("-created_at", "-id")
        )

        active_orders = HospitalMedicationOrder.objects.filter(
            clinic_id__in=accessible_clinic_ids(request.user),
            is_active=True,
            hospital_stay__status=HospitalStay.Status.ADMITTED,
        )
        overdue_medication_count = 0
        for order in active_orders:
            if order.ends_at and order.ends_at < now:
                continue
            last_given = (
                HospitalMedicationAdministration.objects.filter(
                    clinic_id__in=accessible_clinic_ids(request.user),
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
                overdue_medication_count += 1

        admissions = []
        for stay in admissions_qs[:100]:
            admissions.append(
                {
                    "hospital_stay_id": stay.id,
                    "patient_id": stay.patient_id,
                    "patient_name": str(stay.patient),
                    "attending_vet_id": stay.attending_vet_id,
                    "admitted_at": stay.admitted_at.isoformat() if stay.admitted_at else None,
                    "reason": stay.reason,
                    "cage_or_room": stay.cage_or_room,
                }
            )

        discharges = []
        for stay in discharges_qs[:100]:
            discharges.append(
                {
                    "hospital_stay_id": stay.id,
                    "patient_id": stay.patient_id,
                    "patient_name": str(stay.patient),
                    "attending_vet_id": stay.attending_vet_id,
                    "discharged_at": stay.discharged_at.isoformat() if stay.discharged_at else None,
                    "discharge_notes": stay.discharge_notes,
                }
            )

        open_high_tasks = []
        for task in open_high_tasks_qs[:100]:
            open_high_tasks.append(
                {
                    "task_id": task.id,
                    "hospital_stay_id": task.hospital_stay_id,
                    "patient_id": task.hospital_stay.patient_id,
                    "patient_name": str(task.hospital_stay.patient),
                    "title": task.title,
                    "status": task.status,
                    "due_at": task.due_at.isoformat() if task.due_at else None,
                }
            )

        latest_notes = []
        for note in latest_notes_qs[:100]:
            latest_notes.append(
                {
                    "note_id": note.id,
                    "hospital_stay_id": note.hospital_stay_id,
                    "patient_id": note.hospital_stay.patient_id,
                    "patient_name": str(note.hospital_stay.patient),
                    "created_at": note.created_at.isoformat(),
                    "created_by_id": note.created_by_id,
                    "note_type": note.note_type,
                    "note": note.note,
                }
            )

        return Response(
            {
                "now": now.isoformat(),
                "since": since.isoformat(),
                "hours": hours_int,
                "summary": {
                    "admissions_count": admissions_qs.count(),
                    "discharges_count": discharges_qs.count(),
                    "open_high_tasks_count": open_high_tasks_qs.count(),
                    "latest_notes_count": latest_notes_qs.count(),
                    "overdue_medication_orders_count": overdue_medication_count,
                },
                "admissions": admissions,
                "discharges": discharges,
                "open_high_tasks": open_high_tasks,
                "latest_notes": latest_notes,
            },
            status=200,
        )

    @action(detail=False, methods=["get"], url_path="kpi-analytics")
    def kpi_analytics(self, request):
        """
        Hospitalization KPI analytics for operations/admin.
        """
        hours = request.query_params.get("hours", "24")
        export = (request.query_params.get("export") or "").strip().lower()
        try:
            hours_int = int(hours)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid hours."}, status=400)
        if hours_int < 1 or hours_int > 24 * 90:
            return Response({"detail": "hours must be between 1 and 2160."}, status=400)

        now = timezone.now()
        since = now - timedelta(hours=hours_int)

        discharged_stays = HospitalStay.objects.filter(
            clinic_id__in=accessible_clinic_ids(request.user),
            status=HospitalStay.Status.DISCHARGED,
            discharged_at__isnull=False,
            discharged_at__gte=since,
            discharged_at__lte=now,
        )
        discharged_count = discharged_stays.count()

        avg_stay_hours = 0.0
        if discharged_count:
            total_seconds = 0.0
            with_summary_count = 0
            finalized_summary_count = 0
            for stay in discharged_stays:
                total_seconds += max((stay.discharged_at - stay.admitted_at).total_seconds(), 0.0)
                summary = HospitalDischargeSummary.objects.filter(
                    clinic_id__in=accessible_clinic_ids(request.user),
                    hospital_stay=stay,
                ).first()
                if summary:
                    with_summary_count += 1
                    if summary.finalized_at:
                        finalized_summary_count += 1
            avg_stay_hours = round(total_seconds / discharged_count / 3600.0, 2)
            summary_completion_pct = round((with_summary_count / discharged_count) * 100.0, 2)
            finalized_summary_pct = round((finalized_summary_count / discharged_count) * 100.0, 2)
        else:
            summary_completion_pct = 0.0
            finalized_summary_pct = 0.0

        active_stays_count = HospitalStay.objects.filter(
            clinic_id__in=accessible_clinic_ids(request.user),
            status=HospitalStay.Status.ADMITTED,
        ).count()

        tasks_in_period = HospitalStayTask.objects.filter(
            clinic_id__in=accessible_clinic_ids(request.user),
            created_at__gte=since,
            created_at__lte=now,
        )
        tasks_total = tasks_in_period.count()
        tasks_completed = tasks_in_period.filter(status=HospitalStayTask.Status.COMPLETED).count()
        task_completion_pct = (
            round((tasks_completed / tasks_total) * 100.0, 2) if tasks_total else 0.0
        )

        overdue_medication_orders_count = 0
        active_orders = HospitalMedicationOrder.objects.filter(
            clinic_id__in=accessible_clinic_ids(request.user),
            is_active=True,
            hospital_stay__status=HospitalStay.Status.ADMITTED,
        )
        for order in active_orders:
            if order.ends_at and order.ends_at < now:
                continue
            last_given = (
                HospitalMedicationAdministration.objects.filter(
                    clinic_id__in=accessible_clinic_ids(request.user),
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
                overdue_medication_orders_count += 1

        payload = {
            "now": now.isoformat(),
            "since": since.isoformat(),
            "hours": hours_int,
            "kpis": {
                "discharged_count": discharged_count,
                "active_stays_count": active_stays_count,
                "avg_stay_hours": avg_stay_hours,
                "summary_completion_pct": summary_completion_pct,
                "finalized_summary_pct": finalized_summary_pct,
                "task_completion_pct": task_completion_pct,
                "overdue_medication_orders_count": overdue_medication_orders_count,
            },
        }

        if export == "csv":
            buffer = StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["metric", "value"])
            for key, value in payload["kpis"].items():
                writer.writerow([key, value])
            response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = (
                f'attachment; filename="hospital_kpi_analytics_{now:%Y%m%d_%H%M%S}.csv"'
            )
            return response

        return Response(payload, status=200)

    def _build_discharge_summary_draft(self, stay: HospitalStay) -> dict:
        latest_note = (
            HospitalStayNote.objects.filter(
                clinic_id__in=accessible_clinic_ids(self.request.user),
                hospital_stay=stay,
            )
            .order_by("-created_at", "-id")
            .first()
        )
        completed_tasks = HospitalStayTask.objects.filter(
            clinic_id__in=accessible_clinic_ids(self.request.user),
            hospital_stay=stay,
            status=HospitalStayTask.Status.COMPLETED,
        ).order_by("-updated_at", "-id")[:5]
        active_medications = HospitalMedicationOrder.objects.filter(
            clinic_id__in=accessible_clinic_ids(self.request.user),
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
            clinic_id__in=accessible_clinic_ids(self.request.user),
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
            clinic_id__in=accessible_clinic_ids(self.request.user),
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
            clinic_id__in=accessible_clinic_ids(self.request.user),
            hospital_stay=stay,
            is_active=True,
        )
        for order in active_orders:
            if order.ends_at and order.ends_at < now:
                continue
            last_given = (
                HospitalMedicationAdministration.objects.filter(
                    clinic_id__in=accessible_clinic_ids(self.request.user),
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
        before = {
            "status": stay.status,
            "discharged_at": stay.discharged_at,
            "discharge_notes": stay.discharge_notes,
        }
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
        log_audit_event(
            clinic_id=stay.clinic_id,
            actor=request.user,
            action="hospital_stay_discharged",
            entity_type="hospital_stay",
            entity_id=stay.id,
            before=before,
            after={
                "status": stay.status,
                "discharged_at": stay.discharged_at.isoformat() if stay.discharged_at else None,
                "discharge_notes": stay.discharge_notes,
            },
        )
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
            clinic_id=stay.clinic_id,
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
        before = HospitalDischargeSummaryReadSerializer(summary).data if summary else {}
        if summary:
            summary = serializer.save()
        else:
            cid = clinic_id_for_mutation(
                request.user, request=request, instance_clinic_id=stay.clinic_id
            )
            summary = serializer.save(
                clinic_id=cid,
                hospital_stay=stay,
                generated_by=request.user,
            )
        data = HospitalDischargeSummaryReadSerializer(summary).data
        data["source"] = "saved"
        log_audit_event(
            clinic_id=summary.clinic_id,
            actor=request.user,
            action="hospital_discharge_summary_saved",
            entity_type="hospital_discharge_summary",
            entity_id=summary.id,
            before=before,
            after=HospitalDischargeSummaryReadSerializer(summary).data,
            metadata={"hospital_stay_id": stay.id},
        )
        return Response(data, status=200)

    @action(detail=True, methods=["post"], url_path="discharge-summary/finalize")
    def finalize_discharge_summary(self, request, pk=None):
        stay = self.get_object()
        summary = HospitalDischargeSummary.objects.filter(
            clinic_id__in=accessible_clinic_ids(request.user),
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
        before = {
            "finalized_at": summary.finalized_at.isoformat() if summary.finalized_at else None
        }
        summary.finalized_at = timezone.now()
        summary.generated_by = request.user
        summary.save(update_fields=["finalized_at", "generated_by", "updated_at"])
        data = HospitalDischargeSummaryReadSerializer(summary).data
        data["source"] = "saved"
        log_audit_event(
            clinic_id=summary.clinic_id,
            actor=request.user,
            action="hospital_discharge_summary_finalized",
            entity_type="hospital_discharge_summary",
            entity_id=summary.id,
            before=before,
            after={
                "finalized_at": summary.finalized_at.isoformat() if summary.finalized_at else None
            },
            metadata={"hospital_stay_id": stay.id},
        )
        return Response(data, status=200)

    @action(detail=True, methods=["get"], url_path="discharge-summary/pdf")
    def discharge_summary_pdf(self, request, pk=None):
        stay = self.get_object()
        summary = HospitalDischargeSummary.objects.filter(
            clinic_id__in=accessible_clinic_ids(request.user),
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

    @action(detail=True, methods=["get"], url_path="discharge-packet")
    def discharge_packet(self, request, pk=None):
        """
        Aggregated payload for discharge workflow:
        - stay summary context
        - discharge summary
        - discharge medication list
        - direct URL to generated PDF endpoint
        """
        stay = self.get_object()
        summary = HospitalDischargeSummary.objects.filter(
            clinic_id__in=accessible_clinic_ids(request.user),
            hospital_stay=stay,
        ).first()
        if not summary:
            return Response({"detail": "Discharge summary not found."}, status=404)

        summary_data = HospitalDischargeSummaryReadSerializer(summary).data
        pdf_url = request.build_absolute_uri(
            f"/api/hospital-stays/{stay.id}/discharge-summary/pdf/"
        )
        return Response(
            {
                "hospital_stay": {
                    "id": stay.id,
                    "patient_id": stay.patient_id,
                    "attending_vet_id": stay.attending_vet_id,
                    "admitted_at": stay.admitted_at.isoformat() if stay.admitted_at else None,
                    "discharged_at": stay.discharged_at.isoformat() if stay.discharged_at else None,
                    "discharge_notes": stay.discharge_notes,
                },
                "discharge_summary": summary_data,
                "medications_on_discharge": summary_data.get("medications_on_discharge", []),
                "follow_up_date": summary_data.get("follow_up_date"),
                "pdf_download_url": pdf_url,
            },
            status=200,
        )

    @action(detail=True, methods=["get", "post"], url_path="notes")
    def notes(self, request, pk=None):
        stay = self.get_object()
        if request.method == "GET":
            items = HospitalStayNote.objects.filter(
                clinic_id__in=accessible_clinic_ids(request.user),
                hospital_stay=stay,
            ).order_by("-created_at", "-id")
            return Response(HospitalStayNoteReadSerializer(items, many=True).data, status=200)

        serializer = HospitalStayNoteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.save(
            clinic_id=stay.clinic_id,
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
            clinic_id__in=accessible_clinic_ids(request.user),
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
                clinic_id__in=accessible_clinic_ids(request.user),
                hospital_stay=stay,
            ).order_by("status", "due_at", "id")
            return Response(HospitalStayTaskReadSerializer(items, many=True).data, status=200)

        serializer = HospitalStayTaskWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.save(
            clinic_id=stay.clinic_id,
            hospital_stay=stay,
            created_by=request.user,
        )
        if task.status == HospitalStayTask.Status.COMPLETED:
            task.completed_at = timezone.now()
            task.completed_by = request.user
            task.save(update_fields=["completed_at", "completed_by", "updated_at"])
            log_audit_event(
                clinic_id=task.clinic_id,
                actor=request.user,
                action="hospital_task_completed",
                entity_type="hospital_stay_task",
                entity_id=task.id,
                before={"status": HospitalStayTask.Status.PENDING},
                after={
                    "status": task.status,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                },
                metadata={"hospital_stay_id": stay.id},
            )
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
            clinic_id__in=accessible_clinic_ids(request.user),
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
            log_audit_event(
                clinic_id=task.clinic_id,
                actor=request.user,
                action="hospital_task_completed",
                entity_type="hospital_stay_task",
                entity_id=task.id,
                before={"status": previous_status},
                after={
                    "status": task.status,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                },
                metadata={"hospital_stay_id": stay.id},
            )
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
                clinic_id__in=accessible_clinic_ids(request.user),
                hospital_stay=stay,
            ).order_by("-created_at", "-id")
            return Response(
                HospitalMedicationOrderReadSerializer(items, many=True).data, status=200
            )

        serializer = HospitalMedicationOrderWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        medication = serializer.save(
            clinic_id=stay.clinic_id,
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
            clinic_id__in=accessible_clinic_ids(request.user),
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
                        clinic_id__in=accessible_clinic_ids(request.user),
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
                                clinic_id=order.clinic_id,
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
            clinic_id__in=accessible_clinic_ids(request.user),
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
            clinic_id__in=accessible_clinic_ids(request.user),
            hospital_stay=stay,
        ).first()
        if not medication:
            return Response({"detail": "Medication order not found."}, status=404)

        if request.method == "GET":
            items = HospitalMedicationAdministration.objects.filter(
                clinic_id__in=accessible_clinic_ids(request.user),
                medication_order=medication,
            ).order_by("-scheduled_for", "-created_at", "-id")
            return Response(
                HospitalMedicationAdministrationReadSerializer(items, many=True).data,
                status=200,
            )

        serializer = HospitalMedicationAdministrationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        administration = serializer.save(
            clinic_id=medication.clinic_id,
            medication_order=medication,
        )
        if administration.status == HospitalMedicationAdministration.Status.GIVEN:
            if administration.administered_at is None:
                administration.administered_at = timezone.now()
            administration.administered_by = request.user
            administration.save(update_fields=["administered_at", "administered_by", "updated_at"])
        log_audit_event(
            clinic_id=administration.clinic_id,
            actor=request.user,
            action="hospital_medication_admin_created",
            entity_type="hospital_medication_administration",
            entity_id=administration.id,
            before={},
            after={
                "status": administration.status,
                "scheduled_for": (
                    administration.scheduled_for.isoformat()
                    if administration.scheduled_for
                    else None
                ),
                "administered_at": (
                    administration.administered_at.isoformat()
                    if administration.administered_at
                    else None
                ),
            },
            metadata={"hospital_stay_id": stay.id, "medication_order_id": medication.id},
        )
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
            clinic_id__in=accessible_clinic_ids(request.user),
            hospital_stay=stay,
        ).first()
        if not medication:
            return Response({"detail": "Medication order not found."}, status=404)

        administration = HospitalMedicationAdministration.objects.filter(
            id=administration_id,
            clinic_id__in=accessible_clinic_ids(request.user),
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
        if previous_status != administration.status:
            log_audit_event(
                clinic_id=administration.clinic_id,
                actor=request.user,
                action="hospital_medication_admin_status_changed",
                entity_type="hospital_medication_administration",
                entity_id=administration.id,
                before={"status": previous_status},
                after={"status": administration.status},
                metadata={"hospital_stay_id": stay.id, "medication_order_id": medication.id},
            )
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
            clinic_id__in=accessible_clinic_ids(request.user),
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
                    clinic_id__in=accessible_clinic_ids(request.user),
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
