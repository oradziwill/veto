"""Notify clinic staff (in-app) when an owner books via the portal."""

from __future__ import annotations

import logging

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.notifications.services import notify_clinic_staff

logger = logging.getLogger(__name__)


def notify_staff_new_portal_booking(
    *,
    clinic_id: int,
    patient_name: str,
    appointment_id: int,
    vet_id: int,
    starts_at,
) -> None:
    if not getattr(settings, "PORTAL_NOTIFY_STAFF_ON_BOOKING", True):
        return
    try:
        vet = User.objects.filter(pk=vet_id).only("first_name", "last_name", "username").first()
        vet_label = ""
        if vet:
            vet_label = (vet.get_full_name() or vet.username or "").strip() or str(vet_id)
        local_start = timezone.localtime(starts_at).strftime("%Y-%m-%d %H:%M")
        n = notify_clinic_staff(
            clinic_id=clinic_id,
            kind=Notification.Kind.PORTAL_APPOINTMENT_BOOKED,
            title=f"Online booking: {patient_name}",
            body=f"{local_start} — {vet_label}. Visit #{appointment_id}.",
            link_tab="appointments",
        )
        logger.info(
            "portal_booking_staff_notified clinic_id=%s appointment_id=%s recipients=%s",
            clinic_id,
            appointment_id,
            n,
        )
    except Exception:
        logger.exception(
            "portal_booking_staff_notify_failed clinic_id=%s appointment_id=%s",
            clinic_id,
            appointment_id,
        )
