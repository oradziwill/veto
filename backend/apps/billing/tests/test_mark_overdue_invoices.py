"""Tests for mark_overdue_invoices management command."""

import io
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.billing.models import Invoice


@pytest.mark.django_db
def test_mark_overdue_invoices_runs_on_empty_db():
    """Command runs without error when there are no invoices."""
    out = io.StringIO()
    call_command("mark_overdue_invoices", stdout=out)
    assert "0" in out.getvalue() or "No invoices" in out.getvalue()


@pytest.mark.django_db
def test_only_sent_past_due_updated(clinic, client_with_membership):
    """Only sent invoices with due_date < today become overdue."""
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    sent_past = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        status=Invoice.Status.SENT,
        due_date=yesterday,
    )
    sent_future = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        status=Invoice.Status.SENT,
        due_date=tomorrow,
    )
    sent_today = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        status=Invoice.Status.SENT,
        due_date=today,
    )
    draft_past = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        status=Invoice.Status.DRAFT,
        due_date=yesterday,
    )
    paid_past = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        status=Invoice.Status.PAID,
        due_date=yesterday,
    )

    call_command("mark_overdue_invoices")

    sent_past.refresh_from_db()
    sent_future.refresh_from_db()
    sent_today.refresh_from_db()
    draft_past.refresh_from_db()
    paid_past.refresh_from_db()

    assert sent_past.status == Invoice.Status.OVERDUE
    assert sent_future.status == Invoice.Status.SENT
    assert sent_today.status == Invoice.Status.SENT
    assert draft_past.status == Invoice.Status.DRAFT
    assert paid_past.status == Invoice.Status.PAID


@pytest.mark.django_db
def test_logs_count(clinic, client_with_membership):
    """Command logs how many invoices were marked overdue."""
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)

    Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        status=Invoice.Status.SENT,
        due_date=yesterday,
    )
    Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        status=Invoice.Status.SENT,
        due_date=yesterday,
    )

    out = io.StringIO()
    call_command("mark_overdue_invoices", stdout=out)
    text = out.getvalue()
    assert "2" in text or "Marked 2" in text


@pytest.mark.django_db
def test_sent_with_null_due_date_unchanged(clinic, client_with_membership):
    """Sent invoice with due_date=None remains sent."""
    inv = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        status=Invoice.Status.SENT,
        due_date=None,
    )

    call_command("mark_overdue_invoices")

    inv.refresh_from_db()
    assert inv.status == Invoice.Status.SENT
