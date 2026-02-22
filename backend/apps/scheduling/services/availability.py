from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from apps.scheduling.models import Appointment
from apps.scheduling.models_working_hours import VetWorkingHours
from apps.tenancy.models import ClinicHoliday
from django.conf import settings
from django.utils import timezone


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime


def _parse_hhmm(value: str) -> time:
    hh, mm = value.split(":")
    return time(hour=int(hh), minute=int(mm))


def _merge_intervals(intervals: list[Interval]) -> list[Interval]:
    if not intervals:
        return []

    intervals = sorted(intervals, key=lambda x: x.start)
    merged: list[Interval] = [intervals[0]]

    for it in intervals[1:]:
        last = merged[-1]
        if it.start <= last.end:
            merged[-1] = Interval(start=last.start, end=max(last.end, it.end))
        else:
            merged.append(it)

    return merged


def _subtract(work: Interval, busy: Iterable[Interval]) -> list[Interval]:
    """
    Return pieces of `work` not covered by any busy interval (busy must be merged).
    """
    free: list[Interval] = []
    cursor = work.start

    for b in busy:
        if b.end <= cursor:
            continue
        if b.start >= work.end:
            break

        if b.start > cursor:
            free.append(Interval(start=cursor, end=min(b.start, work.end)))

        cursor = max(cursor, b.end)
        if cursor >= work.end:
            break

    if cursor < work.end:
        free.append(Interval(start=cursor, end=work.end))

    return free


def _round_up(dt: datetime, minutes: int) -> datetime:
    """
    Round datetime up to the next `minutes` boundary.
    """
    if minutes <= 1:
        return dt

    epoch = int(dt.timestamp())
    step = minutes * 60
    rounded = ((epoch + step - 1) // step) * step
    return datetime.fromtimestamp(rounded, tz=dt.tzinfo)


def _split_into_slots(intervals: Iterable[Interval], slot_minutes: int) -> list[Interval]:
    slot = timedelta(minutes=slot_minutes)
    out: list[Interval] = []

    for it in intervals:
        start = _round_up(it.start, slot_minutes)
        while start + slot <= it.end:
            out.append(Interval(start=start, end=start + slot))
            start = start + slot

    return out


def compute_availability(
    *,
    clinic_id: int,
    date_str: str,
    vet_id: int | None,
    room_id: int | None,
    slot_minutes: int | None,
):
    """
    Compute availability for a clinic on a given date.
    - If vet_id is provided: use vet working hours (if configured) for that weekday,
      otherwise fall back to default clinic hours from settings.
    - If room_id is provided: busy intervals are only from appointments in that room.
    - Excludes CANCELLED appointments from busy time.
    - Respects clinic holidays (ClinicHoliday): returns closed_reason + empty slots.
    """
    tz = timezone.get_current_timezone()

    # Parse date
    day = datetime.fromisoformat(date_str).date()

    # Slot length
    slot_minutes_final = int(slot_minutes or getattr(settings, "DEFAULT_SLOT_MINUTES", 30))

    # Clinic closure check
    holiday = (
        ClinicHoliday.objects.filter(
            clinic_id=clinic_id,
            date=day,
            is_active=True,
        )
        .only("id", "reason")
        .first()
    )
    if holiday:
        return {
            "timezone": str(tz),
            "work_intervals": [],
            "work_bounds": None,
            "busy_raw": [],
            "busy_merged": [],
            "free_slots": [],
            "slot_minutes": slot_minutes_final,
            "closed_reason": holiday.reason or "Clinic closed",
        }

    # Defaults from settings
    default_open_t = _parse_hhmm(getattr(settings, "DEFAULT_CLINIC_OPEN_TIME", "09:00"))
    default_close_t = _parse_hhmm(getattr(settings, "DEFAULT_CLINIC_CLOSE_TIME", "17:00"))

    open_t = default_open_t
    close_t = default_close_t

    # Vet-specific hours override (MVP: take the first active interval for that weekday)
    if vet_id is not None:
        weekday = day.weekday()  # Monday=0 ... Sunday=6
        wh = (
            VetWorkingHours.objects.filter(vet_id=vet_id, weekday=weekday, is_active=True)
            .order_by("start_time")
            .first()
        )
        if wh:
            if wh.is_day_off:
                return {
                    "timezone": str(tz),
                    "work_intervals": [],
                    "work_bounds": None,
                    "busy_raw": [],
                    "busy_merged": [],
                    "free_slots": [],
                    "slot_minutes": slot_minutes_final,
                    "closed_reason": "Vet is off",
                }
            open_t = wh.start_time
            close_t = wh.end_time

    # Build work interval in current TZ
    work_start = timezone.make_aware(datetime.combine(day, open_t), tz)
    work_end = timezone.make_aware(datetime.combine(day, close_t), tz)

    # Edge case: invalid bounds (should not happen if data is clean)
    if work_end <= work_start:
        return {
            "timezone": str(tz),
            "work_intervals": [],
            "work_bounds": None,
            "busy_raw": [],
            "busy_merged": [],
            "free_slots": [],
            "slot_minutes": slot_minutes_final,
            "closed_reason": "Invalid working hours configuration",
        }

    work = Interval(start=work_start, end=work_end)

    # Query busy appointments that overlap the work interval
    qs = (
        Appointment.objects.filter(
            clinic_id=clinic_id,
            starts_at__lt=work.end,
            ends_at__gt=work.start,
        )
        .exclude(status=Appointment.Status.CANCELLED)
        .only("id", "starts_at", "ends_at", "vet_id", "room_id")
    )

    if vet_id is not None:
        qs = qs.filter(vet_id=vet_id)
    if room_id is not None:
        qs = qs.filter(room_id=room_id)

    busy_raw: list[tuple[int, Interval]] = [
        (a.id, Interval(start=a.starts_at, end=a.ends_at)) for a in qs
    ]
    busy_merged = _merge_intervals([b for _, b in busy_raw])
    free_blocks = _subtract(work, busy_merged)
    free_slots = _split_into_slots(free_blocks, slot_minutes_final)

    # work is a single Interval (bounds for the day)
    work_bounds = work
    work_intervals = [work_bounds]

    return {
        "timezone": str(tz),
        "work_intervals": work_intervals,
        "work_bounds": work_bounds,
        "busy_raw": busy_raw,
        "busy_merged": busy_merged,
        "free_slots": free_slots,
        "slot_minutes": slot_minutes_final,
        "closed_reason": None,
    }
