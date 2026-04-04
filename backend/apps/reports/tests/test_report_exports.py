from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.billing.models import Invoice, InvoiceLine
from apps.reports.models import ReportExportJob
from apps.tenancy.models import Clinic


@pytest.mark.django_db
def test_create_report_export_job_admin_only(api_client, clinic_admin, receptionist):
    api_client.force_authenticate(user=receptionist)
    forbidden = api_client.post(
        reverse("report-exports-list"),
        {"report_type": ReportExportJob.ReportType.REVENUE_SUMMARY, "params": {}},
        format="json",
    )
    assert forbidden.status_code == 403

    api_client.force_authenticate(user=clinic_admin)
    ok = api_client.post(
        reverse("report-exports-list"),
        {"report_type": ReportExportJob.ReportType.REVENUE_SUMMARY, "params": {}},
        format="json",
    )
    assert ok.status_code == 201
    assert ok.data["status"] == ReportExportJob.Status.PENDING


@pytest.mark.django_db
@override_settings(RQ_REPORT_EXPORT_ENQUEUE=True)
def test_create_report_export_enqueues_when_enabled(api_client, clinic_admin):
    with patch("django_rq.get_queue") as gq:
        gq.return_value.enqueue = MagicMock()
        api_client.force_authenticate(user=clinic_admin)
        ok = api_client.post(
            reverse("report-exports-list"),
            {"report_type": ReportExportJob.ReportType.REVENUE_SUMMARY, "params": {}},
            format="json",
        )
        assert ok.status_code == 201
        gq.return_value.enqueue.assert_called_once()


@pytest.mark.django_db
def test_execute_report_export_job_by_id(clinic, clinic_admin):
    from apps.reports.job_runner import execute_report_export_job_by_id

    job = ReportExportJob.objects.create(
        clinic=clinic,
        requested_by=clinic_admin,
        report_type=ReportExportJob.ReportType.REVENUE_SUMMARY,
        params={},
        status=ReportExportJob.Status.PENDING,
    )
    assert execute_report_export_job_by_id(job.id) == "processed"
    job.refresh_from_db()
    assert job.status == ReportExportJob.Status.COMPLETED


@pytest.mark.django_db
def test_process_pending_and_download_report(
    api_client, clinic_admin, clinic, patient, client_with_membership
):
    invoice = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        status=Invoice.Status.SENT,
    )
    InvoiceLine.objects.create(
        invoice=invoice,
        description="Consultation",
        quantity=1,
        unit_price=100,
    )
    job = ReportExportJob.objects.create(
        clinic=clinic,
        requested_by=clinic_admin,
        report_type=ReportExportJob.ReportType.REVENUE_SUMMARY,
        params={},
        status=ReportExportJob.Status.PENDING,
    )

    api_client.force_authenticate(user=clinic_admin)
    processed = api_client.post(
        reverse("report-exports-process-pending"),
        {"limit": 10},
        format="json",
    )
    assert processed.status_code == 200
    assert processed.data["processed"] == 1

    job.refresh_from_db()
    assert job.status == ReportExportJob.Status.COMPLETED
    assert job.file_content

    download = api_client.get(reverse("report-exports-download", args=[job.id]))
    assert download.status_code == 200
    assert download["Content-Type"].startswith("text/csv")
    assert "invoice_id,created_date,status,line_total,payments_count" in download.content.decode(
        "utf-8"
    )
    assert AuditLog.objects.filter(
        clinic_id=clinic.id,
        action="report_export_job_downloaded",
        entity_type="report_export_job",
        entity_id=str(job.id),
    ).exists()


@pytest.mark.django_db
def test_report_exports_are_clinic_scoped(api_client):
    clinic1 = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    clinic2 = Clinic.objects.create(name="C2", address="a2", phone="p2", email="e2@e.com")
    admin1 = User.objects.create_user(
        username="admin_reports_1",
        password="pass",
        clinic=clinic1,
        is_staff=True,
        role=User.Role.ADMIN,
    )
    admin2 = User.objects.create_user(
        username="admin_reports_2",
        password="pass",
        clinic=clinic2,
        is_staff=True,
        role=User.Role.ADMIN,
    )

    ReportExportJob.objects.create(
        clinic=clinic1,
        requested_by=admin1,
        report_type=ReportExportJob.ReportType.REVENUE_SUMMARY,
        params={},
        status=ReportExportJob.Status.PENDING,
    )
    ReportExportJob.objects.create(
        clinic=clinic2,
        requested_by=admin2,
        report_type=ReportExportJob.ReportType.REMINDER_ANALYTICS,
        params={},
        status=ReportExportJob.Status.PENDING,
    )

    api_client.force_authenticate(user=admin1)
    response = api_client.get(reverse("report-exports-list"))
    assert response.status_code == 200
    assert len(response.data) == 1


@pytest.mark.django_db
def test_accounting_invoice_lines_export_csv(
    api_client, clinic_admin, clinic, patient, client_with_membership
):
    invoice = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        status=Invoice.Status.SENT,
        invoice_number="FV/2026/001",
        currency="PLN",
    )
    InvoiceLine.objects.create(
        invoice=invoice,
        description="Consultation",
        quantity=1,
        unit_price=100,
        vat_rate="8",
        unit="usł",
    )
    job = ReportExportJob.objects.create(
        clinic=clinic,
        requested_by=clinic_admin,
        report_type=ReportExportJob.ReportType.ACCOUNTING_INVOICE_LINES,
        params={},
        status=ReportExportJob.Status.PENDING,
    )

    api_client.force_authenticate(user=clinic_admin)
    processed = api_client.post(
        reverse("report-exports-process-pending"),
        {"limit": 10},
        format="json",
    )
    assert processed.status_code == 200
    assert processed.data["processed"] == 1

    job.refresh_from_db()
    assert job.status == ReportExportJob.Status.COMPLETED
    body = job.file_content
    assert "invoice_id,invoice_number" in body
    assert "line_net,line_vat,line_gross" in body
    assert "FV/2026/001" in body
    assert "Consultation" in body
    assert str(invoice.id) in body
