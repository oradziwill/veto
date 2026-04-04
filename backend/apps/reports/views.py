from datetime import datetime, timedelta
from datetime import time as dt_time

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsClinicAdmin, IsStaffOrVet
from apps.audit.services import log_audit_event
from apps.scheduling.models import Appointment
from apps.tenancy.access import (
    accessible_clinic_ids,
    clinic_id_for_mutation,
)

from .job_runner import execute_report_export_job_by_id
from .models import ReportExportJob
from .rq_tasks import try_enqueue_report_export_job
from .serializers import ReportExportJobCreateSerializer, ReportExportJobReadSerializer


class PortalBookingMetricsView(APIView):
    """
    GET /api/reports/portal-booking-metrics/?from=YYYY-MM-DD&to=YYYY-MM-DD
    Count appointments by starts_at in range: total vs booked_via_portal.
    """

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get(self, request):
        clinic_id = request.user.clinic_id
        from_str = (
            request.query_params.get("from") or request.query_params.get("date_from") or ""
        ).strip()
        to_str = (
            request.query_params.get("to") or request.query_params.get("date_to") or ""
        ).strip()
        today = timezone.localdate()
        if not from_str:
            d_from = today - timedelta(days=30)
        else:
            try:
                d_from = datetime.strptime(from_str, "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "Invalid from date (use YYYY-MM-DD)."}, status=400)
        if not to_str:
            d_to = today
        else:
            try:
                d_to = datetime.strptime(to_str, "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "Invalid to date (use YYYY-MM-DD)."}, status=400)
        if d_from > d_to:
            return Response({"detail": "from must be on or before to."}, status=400)

        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.combine(d_from, dt_time.min), tz)
        end_excl = timezone.make_aware(datetime.combine(d_to + timedelta(days=1), dt_time.min), tz)
        qs = Appointment.objects.filter(
            clinic_id=clinic_id,
            starts_at__gte=start,
            starts_at__lt=end_excl,
        )
        total = qs.count()
        portal_n = qs.filter(booked_via_portal=True).count()
        share = (portal_n / total) if total else 0.0
        return Response(
            {
                "from": d_from.isoformat(),
                "to": d_to.isoformat(),
                "appointments_total": total,
                "appointments_booked_via_portal": portal_n,
                "share_portal": round(share, 4),
            }
        )


class ReportExportJobViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsClinicAdmin]

    def get_queryset(self):
        return ReportExportJob.objects.filter(
            clinic_id__in=accessible_clinic_ids(self.request.user)
        ).order_by("-created_at", "-id")

    def get_serializer_class(self):
        if self.action == "create":
            return ReportExportJobCreateSerializer
        return ReportExportJobReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cid = clinic_id_for_mutation(request.user, request=request, instance_clinic_id=None)
        job = ReportExportJob.objects.create(
            clinic_id=cid,
            requested_by=request.user,
            report_type=serializer.validated_data["report_type"],
            params=serializer.validated_data.get("params") or {},
            status=ReportExportJob.Status.PENDING,
        )
        log_audit_event(
            clinic_id=job.clinic_id,
            actor=request.user,
            action="report_export_job_created",
            entity_type="report_export_job",
            entity_id=job.id,
            after={"report_type": job.report_type, "status": job.status},
        )
        try_enqueue_report_export_job(job.id)
        return Response(ReportExportJobReadSerializer(job).data, status=201)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        job = self.get_object()
        if job.status != ReportExportJob.Status.COMPLETED or not job.file_content:
            return Response(
                {"detail": "Report is not ready for download."},
                status=status.HTTP_409_CONFLICT,
            )
        log_audit_event(
            clinic_id=job.clinic_id,
            actor=request.user,
            action="report_export_job_downloaded",
            entity_type="report_export_job",
            entity_id=job.id,
            metadata={"report_type": job.report_type, "file_name": job.file_name or ""},
        )
        response = HttpResponse(job.file_content, content_type=f"{job.content_type}; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{job.file_name or "report.csv"}"'
        return response

    @action(detail=False, methods=["post"], url_path="process-pending")
    def process_pending(self, request):
        limit = request.data.get("limit", 20)
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            return Response({"detail": "limit must be an integer."}, status=400)
        if limit < 1 or limit > 200:
            return Response({"detail": "limit must be between 1 and 200."}, status=400)

        processed = 0
        failed = 0
        skipped = 0
        jobs = list(
            ReportExportJob.objects.filter(
                clinic_id__in=accessible_clinic_ids(request.user),
                status=ReportExportJob.Status.PENDING,
            ).order_by("created_at", "id")[:limit]
        )
        for job in jobs:
            result = execute_report_export_job_by_id(job.id)
            if result == "processed":
                processed += 1
            elif result == "failed":
                failed += 1
            else:
                skipped += 1

        return Response(
            {"processed": processed, "failed": failed, "skipped": skipped},
            status=200,
        )
