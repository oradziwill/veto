"""Tests for GET /api/billing/revenue-summary/ (admin-only revenue summary)."""

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.models import Invoice, InvoiceLine, Payment
from apps.clients.models import Client, ClientClinic
from apps.tenancy.models import Clinic


@pytest.mark.django_db
def test_revenue_summary_unauthenticated(api_client):
    """Unauthenticated request returns 401."""
    r = api_client.get("/api/billing/revenue-summary/")
    assert r.status_code == 401


@pytest.mark.django_db
def test_revenue_summary_admin_only(clinic_admin, receptionist, api_client):
    """Non-admin gets 403; admin gets 200."""
    api_client.force_authenticate(user=receptionist)
    r = api_client.get("/api/billing/revenue-summary/")
    assert r.status_code == 403

    api_client.force_authenticate(user=clinic_admin)
    r = api_client.get("/api/billing/revenue-summary/")
    assert r.status_code == 200
    assert "total_invoiced" in r.data
    assert "by_period" in r.data


@pytest.mark.django_db
def test_revenue_summary_scoped_to_clinic(
    clinic,
    clinic_admin,
    client_with_membership,
    patient,
    api_client,
):
    """Response only includes data for the authenticated user's clinic."""
    # Clinic A (clinic_admin's clinic): one invoice 100
    inv_a = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        status="sent",
    )
    InvoiceLine.objects.create(
        invoice=inv_a,
        description="Consultation",
        quantity=1,
        unit_price=100,
    )
    Invoice.objects.filter(pk=inv_a.pk).update(
        created_at=timezone.datetime(2026, 2, 15, 10, 0, 0, tzinfo=timezone.UTC)
    )

    # Clinic B: different clinic and admin, invoice 999
    clinic_b = Clinic.objects.create(
        name="Other Clinic",
        address="Other St",
        phone="+0000000000",
        email="other@clinic.com",
    )
    client_b = Client.objects.create(
        first_name="Jane",
        last_name="Other",
        phone="+9999999999",
        email="jane@other.com",
    )
    ClientClinic.objects.create(client=client_b, clinic=clinic_b, is_active=True)
    admin_b = User.objects.create_user(
        username="admin_b",
        password="pass",
        clinic=clinic_b,
        role=User.Role.ADMIN,
    )
    inv_b = Invoice.objects.create(
        clinic=clinic_b,
        client=client_b,
        status="sent",
    )
    InvoiceLine.objects.create(
        invoice=inv_b,
        description="Service",
        quantity=1,
        unit_price=999,
    )
    Invoice.objects.filter(pk=inv_b.pk).update(
        created_at=timezone.datetime(2026, 2, 15, 10, 0, 0, tzinfo=timezone.UTC)
    )

    api_client.force_authenticate(user=clinic_admin)
    r = api_client.get(
        "/api/billing/revenue-summary/",
        {"from": "2026-02-01", "to": "2026-02-28", "period": "monthly"},
    )
    assert r.status_code == 200
    assert r.data["total_invoiced"] == "100.00"
    assert r.data["total_paid"] == "0.00"
    assert r.data["total_outstanding"] == "100.00"

    api_client.force_authenticate(user=admin_b)
    r = api_client.get(
        "/api/billing/revenue-summary/",
        {"from": "2026-02-01", "to": "2026-02-28", "period": "monthly"},
    )
    assert r.status_code == 200
    assert r.data["total_invoiced"] == "999.00"


@pytest.mark.django_db
def test_revenue_summary_totals(
    clinic_admin,
    client_with_membership,
    patient,
    api_client,
):
    """Totals match one invoice with partial payment."""
    invoice = Invoice.objects.create(
        clinic=clinic_admin.clinic,
        client=client_with_membership,
        patient=patient,
        status="sent",
    )
    InvoiceLine.objects.create(
        invoice=invoice,
        description="Consultation",
        quantity=1,
        unit_price=500,
    )
    Invoice.objects.filter(pk=invoice.pk).update(
        created_at=timezone.datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.UTC)
    )
    Payment.objects.create(
        invoice=invoice,
        amount=200,
        status=Payment.Status.COMPLETED,
    )
    Payment.objects.filter(invoice=invoice).update(
        paid_at=timezone.datetime(2026, 3, 10, 14, 0, 0, tzinfo=timezone.UTC)
    )

    api_client.force_authenticate(user=clinic_admin)
    r = api_client.get(
        "/api/billing/revenue-summary/",
        {"from": "2026-03-01", "to": "2026-03-31", "period": "monthly"},
    )
    assert r.status_code == 200
    assert r.data["total_invoiced"] == "500.00"
    assert r.data["total_paid"] == "200.00"
    assert r.data["total_outstanding"] == "300.00"


@pytest.mark.django_db
def test_revenue_summary_by_period_monthly(
    clinic_admin,
    client_with_membership,
    patient,
    api_client,
):
    """Monthly by_period has correct labels and amounts."""
    # Jan 2026
    inv1 = Invoice.objects.create(
        clinic=clinic_admin.clinic,
        client=client_with_membership,
        patient=patient,
        status="sent",
    )
    InvoiceLine.objects.create(
        invoice=inv1,
        description="Jan service",
        quantity=1,
        unit_price=100,
    )
    Invoice.objects.filter(pk=inv1.pk).update(
        created_at=timezone.datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.UTC)
    )
    # Feb 2026
    inv2 = Invoice.objects.create(
        clinic=clinic_admin.clinic,
        client=client_with_membership,
        patient=patient,
        status="sent",
    )
    InvoiceLine.objects.create(
        invoice=inv2,
        description="Feb service",
        quantity=1,
        unit_price=200,
    )
    Invoice.objects.filter(pk=inv2.pk).update(
        created_at=timezone.datetime(2026, 2, 20, 10, 0, 0, tzinfo=timezone.UTC)
    )
    Payment.objects.create(
        invoice=inv2,
        amount=200,
        status=Payment.Status.COMPLETED,
    )
    Payment.objects.filter(invoice=inv2).update(
        paid_at=timezone.datetime(2026, 2, 21, 10, 0, 0, tzinfo=timezone.UTC)
    )

    api_client.force_authenticate(user=clinic_admin)
    r = api_client.get(
        "/api/billing/revenue-summary/",
        {"from": "2026-01-01", "to": "2026-02-28", "period": "monthly"},
    )
    assert r.status_code == 200
    by_period = {p["label"]: p for p in r.data["by_period"]}
    assert "2026-01" in by_period
    assert "2026-02" in by_period
    assert by_period["2026-01"]["invoiced"] == "100.00"
    assert by_period["2026-01"]["paid"] == "0.00"
    assert by_period["2026-02"]["invoiced"] == "200.00"
    assert by_period["2026-02"]["paid"] == "200.00"


@pytest.mark.django_db
def test_revenue_summary_by_period_daily(
    clinic_admin,
    client_with_membership,
    patient,
    api_client,
):
    """Daily by_period has correct date labels."""
    inv = Invoice.objects.create(
        clinic=clinic_admin.clinic,
        client=client_with_membership,
        patient=patient,
        status="sent",
    )
    InvoiceLine.objects.create(
        invoice=inv,
        description="Service",
        quantity=1,
        unit_price=75,
    )
    Invoice.objects.filter(pk=inv.pk).update(
        created_at=timezone.datetime(2026, 4, 5, 10, 0, 0, tzinfo=timezone.UTC)
    )

    api_client.force_authenticate(user=clinic_admin)
    r = api_client.get(
        "/api/billing/revenue-summary/",
        {"from": "2026-04-05", "to": "2026-04-05", "period": "daily"},
    )
    assert r.status_code == 200
    assert len(r.data["by_period"]) == 1
    assert r.data["by_period"][0]["label"] == "2026-04-05"
    assert r.data["by_period"][0]["invoiced"] == "75.00"
    assert r.data["by_period"][0]["paid"] == "0.00"


@pytest.mark.django_db
def test_revenue_summary_excludes_cancelled(
    clinic_admin,
    client_with_membership,
    patient,
    api_client,
):
    """Cancelled invoices are not included in total_invoiced."""
    inv_ok = Invoice.objects.create(
        clinic=clinic_admin.clinic,
        client=client_with_membership,
        patient=patient,
        status="sent",
    )
    InvoiceLine.objects.create(
        invoice=inv_ok,
        description="OK",
        quantity=1,
        unit_price=100,
    )
    inv_cancelled = Invoice.objects.create(
        clinic=clinic_admin.clinic,
        client=client_with_membership,
        patient=patient,
        status=Invoice.Status.CANCELLED,
    )
    InvoiceLine.objects.create(
        invoice=inv_cancelled,
        description="Cancelled",
        quantity=1,
        unit_price=500,
    )
    Invoice.objects.filter(pk=inv_ok.pk).update(
        created_at=timezone.datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.UTC)
    )
    Invoice.objects.filter(pk=inv_cancelled.pk).update(
        created_at=timezone.datetime(2026, 5, 2, 10, 0, 0, tzinfo=timezone.UTC)
    )

    api_client.force_authenticate(user=clinic_admin)
    r = api_client.get(
        "/api/billing/revenue-summary/",
        {"from": "2026-05-01", "to": "2026-05-31", "period": "monthly"},
    )
    assert r.status_code == 200
    assert r.data["total_invoiced"] == "100.00"


@pytest.mark.django_db
def test_revenue_summary_invalid_period(clinic_admin, api_client):
    """Invalid period returns 400."""
    api_client.force_authenticate(user=clinic_admin)
    r = api_client.get("/api/billing/revenue-summary/", {"period": "weekly"})
    assert r.status_code == 400
    assert "Invalid period" in r.data["detail"]
