from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsClinicAdmin
from apps.audit.services import log_audit_event

from .models import ReportExportJob
from .serializers import ReportExportJobCreateSerializer, ReportExportJobReadSerializer
from .services import build_report_csv


class ReportExportJobViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsClinicAdmin]

    def get_queryset(self):
        return ReportExportJob.objects.filter(clinic_id=self.request.user.clinic_id).order_by(
            "-created_at", "-id"
        )

    def get_serializer_class(self):
        if self.action == "create":
            return ReportExportJobCreateSerializer
        return ReportExportJobReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = ReportExportJob.objects.create(
            clinic_id=request.user.clinic_id,
            requested_by=request.user,
            report_type=serializer.validated_data["report_type"],
            params=serializer.validated_data.get("params") or {},
            status=ReportExportJob.Status.PENDING,
        )
        log_audit_event(
            clinic_id=request.user.clinic_id,
            actor=request.user,
            action="report_export_job_created",
            entity_type="report_export_job",
            entity_id=job.id,
            after={"report_type": job.report_type, "status": job.status},
        )
        return Response(ReportExportJobReadSerializer(job).data, status=201)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        job = self.get_object()
        if job.status != ReportExportJob.Status.COMPLETED or not job.file_content:
            return Response(
                {"detail": "Report is not ready for download."},
                status=status.HTTP_409_CONFLICT,
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
        jobs = list(
            ReportExportJob.objects.filter(
                clinic_id=request.user.clinic_id,
                status=ReportExportJob.Status.PENDING,
            ).order_by("created_at", "id")[:limit]
        )
        for job in jobs:
            job.status = ReportExportJob.Status.PROCESSING
            job.error = ""
            job.save(update_fields=["status", "error", "updated_at"])
            try:
                file_name, content = build_report_csv(job)
                job.file_name = file_name
                job.file_content = content
                job.status = ReportExportJob.Status.COMPLETED
                job.completed_at = timezone.now()
                job.save(
                    update_fields=[
                        "file_name",
                        "file_content",
                        "status",
                        "completed_at",
                        "updated_at",
                    ]
                )
                processed += 1
            except Exception as exc:
                job.status = ReportExportJob.Status.FAILED
                job.error = str(exc)
                job.save(update_fields=["status", "error", "updated_at"])
                failed += 1

        return Response({"processed": processed, "failed": failed}, status=200)
