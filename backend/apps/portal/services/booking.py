from __future__ import annotations

from datetime import datetime

from django.conf import settings
from django.utils import timezone

from apps.scheduling.services.availability import compute_availability


def portal_slot_matches_availability(
    *,
    clinic_id: int,
    vet_id: int,
    room_id: int | None,
    starts_at: datetime,
    ends_at: datetime,
    slot_minutes: int | None = None,
) -> bool:
    """
    True if [starts_at, ends_at] exactly matches one computed free slot
    for the vet (and optional room) on that local calendar day.
    """
    if ends_at <= starts_at:
        return False
    if timezone.is_naive(starts_at):
        starts_at = timezone.make_aware(starts_at, timezone.get_current_timezone())
    if timezone.is_naive(ends_at):
        ends_at = timezone.make_aware(ends_at, timezone.get_current_timezone())

    date_str = timezone.localdate(starts_at).isoformat()
    slot_m = (
        slot_minutes if slot_minutes is not None else getattr(settings, "DEFAULT_SLOT_MINUTES", 30)
    )
    data = compute_availability(
        clinic_id=clinic_id,
        date_str=date_str,
        vet_id=vet_id,
        room_id=room_id,
        slot_minutes=slot_m,
    )
    if data.get("closed_reason"):
        return False
    for free in data["free_slots"]:
        if free.start == starts_at and free.end == ends_at:
            return True
    return False
