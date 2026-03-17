from __future__ import annotations

from django.contrib.auth import get_user_model

from apps.notifications.models import Notification

User = get_user_model()


def notify_clinic_staff(
    *,
    clinic_id: int,
    kind: str,
    title: str,
    body: str,
    link_tab: str = "",
) -> int:
    recipients = User.objects.filter(
        clinic_id=clinic_id,
        role__in=[
            User.Role.DOCTOR,
            User.Role.RECEPTIONIST,
            User.Role.ADMIN,
        ],
    ).only("id", "clinic_id")
    rows = [
        Notification(
            recipient_id=user.id,
            clinic_id=clinic_id,
            kind=kind,
            title=title[:160],
            body=body[:500],
            link_tab=(link_tab or "")[:64],
        )
        for user in recipients
    ]
    if not rows:
        return 0
    created = Notification.objects.bulk_create(rows)
    return len(created)
