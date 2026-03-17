from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, time, timedelta

from apps.accounts.models import User
from apps.scheduling.models import Appointment
from apps.scheduling.models_exceptions import VetAvailabilityException
from apps.scheduling.models_working_hours import VetWorkingHours
from apps.tenancy.models import ClinicHoliday
from django.conf import settings
from django.utils import timezone

ACTIVE_APPOINTMENT_STATUSES = (
    Appointment.Status.SCHEDULED,
    Appointment.Status.CONFIRMED,
    Appointment.Status.CHECKED_IN,
)


@dataclass(frozen=True)
class TimeInterval:
    start: datetime
    end: datetime


def _parse_hhmm(value: str) -> time:
    hh, mm = value.split(":")
    return time(hour=int(hh), minute=int(mm))


def _minutes_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> int:
    overlap_start = max(a_start, b_start)
    overlap_end = min(a_end, b_end)
    if overlap_end <= overlap_start:
        return 0
    return int((overlap_end - overlap_start).total_seconds() // 60)


def _daterange(start_date: date_type, end_date: date_type) -> Iterable[date_type]:
    day = start_date
    while day <= end_date:
        yield day
        day = day + timedelta(days=1)


def _day_bounds(day: date_type, tz) -> tuple[datetime, datetime]:
    day_start = timezone.make_aware(datetime.combine(day, time.min), tz)
    day_end = day_start + timedelta(days=1)
    return day_start, day_end


def _is_holiday(clinic_id: int, day: date_type) -> bool:
    return ClinicHoliday.objects.filter(clinic_id=clinic_id, date=day, is_active=True).exists()


def _get_vet_intervals(clinic_id: int, vet_id: int, day: date_type) -> list[TimeInterval]:
    tz = timezone.get_current_timezone()
    if _is_holiday(clinic_id, day):
        return []

    exception = (
        VetAvailabilityException.objects.filter(clinic_id=clinic_id, vet_id=vet_id, date=day)
        .only("is_day_off", "start_time", "end_time")
        .first()
    )
    if exception:
        if exception.is_day_off:
            return []
        if exception.start_time and exception.end_time:
            return [
                TimeInterval(
                    start=timezone.make_aware(datetime.combine(day, exception.start_time), tz),
                    end=timezone.make_aware(datetime.combine(day, exception.end_time), tz),
                )
            ]

    weekday = day.weekday()
    work_rows = list(
        VetWorkingHours.objects.filter(vet_id=vet_id, weekday=weekday, is_active=True)
        .order_by("start_time")
        .only("start_time", "end_time")
    )
    if work_rows:
        return [
            TimeInterval(
                start=timezone.make_aware(datetime.combine(day, row.start_time), tz),
                end=timezone.make_aware(datetime.combine(day, row.end_time), tz),
            )
            for row in work_rows
        ]

    default_open = _parse_hhmm(getattr(settings, "DEFAULT_CLINIC_OPEN_TIME", "09:00"))
    default_close = _parse_hhmm(getattr(settings, "DEFAULT_CLINIC_CLOSE_TIME", "17:00"))
    if default_close <= default_open:
        return []
    return [
        TimeInterval(
            start=timezone.make_aware(datetime.combine(day, default_open), tz),
            end=timezone.make_aware(datetime.combine(day, default_close), tz),
        )
    ]


def _interval_minutes(intervals: Iterable[TimeInterval]) -> int:
    return int(sum((it.end - it.start).total_seconds() // 60 for it in intervals))


def _day_booked_minutes(clinic_id: int, vet_id: int, day: date_type) -> int:
    tz = timezone.get_current_timezone()
    day_start, day_end = _day_bounds(day, tz)
    qs = Appointment.objects.filter(
        clinic_id=clinic_id,
        vet_id=vet_id,
        status__in=ACTIVE_APPOINTMENT_STATUSES,
        starts_at__lt=day_end,
        ends_at__gt=day_start,
    ).only("starts_at", "ends_at")
    return sum(_minutes_overlap(a.starts_at, a.ends_at, day_start, day_end) for a in qs)


def _hour_bucket_minutes(intervals: Iterable[TimeInterval], bucket_start: datetime) -> int:
    bucket_end = bucket_start + timedelta(hours=1)
    return sum(_minutes_overlap(it.start, it.end, bucket_start, bucket_end) for it in intervals)


def _is_slot_free_for_appointment(
    *,
    clinic_id: int,
    vet_id: int,
    room_id: int | None,
    start_at: datetime,
    end_at: datetime,
    exclude_appointment_id: int,
) -> bool:
    overlaps = Appointment.objects.filter(
        clinic_id=clinic_id,
        status__in=ACTIVE_APPOINTMENT_STATUSES,
        starts_at__lt=end_at,
        ends_at__gt=start_at,
    ).exclude(id=exclude_appointment_id)

    if overlaps.filter(vet_id=vet_id).exists():
        return False
    if room_id and overlaps.filter(room_id=room_id).exists():
        return False
    return True


def generate_capacity_insights(
    *,
    clinic_id: int,
    start_date: date_type,
    end_date: date_type,
    granularity: str = "day",
    vet_id: int | None = None,
    overload_threshold_pct: float = 85.0,
) -> dict[str, object]:
    vets = User.objects.filter(clinic_id=clinic_id, is_vet=True).order_by("id")
    if vet_id:
        vets = vets.filter(id=vet_id)

    rows: list[dict[str, object]] = []
    overload_windows: list[dict[str, object]] = []
    by_vet: dict[int, dict[str, object]] = {}
    by_day: dict[str, dict[str, object]] = {}
    tz = timezone.get_current_timezone()

    for vet in vets:
        by_vet[vet.id] = {
            "vet_id": vet.id,
            "vet_name": vet.get_full_name() or vet.username,
            "available_minutes": 0,
            "booked_minutes": 0,
            "utilization_pct": 0.0,
        }
        for day in _daterange(start_date, end_date):
            intervals = _get_vet_intervals(clinic_id, vet.id, day)
            available_minutes_day = _interval_minutes(intervals)
            booked_minutes_day = _day_booked_minutes(clinic_id, vet.id, day)

            if granularity == "hour":
                day_start, _day_end = _day_bounds(day, tz)
                for h in range(24):
                    bucket_start = day_start + timedelta(hours=h)
                    available_minutes = _hour_bucket_minutes(intervals, bucket_start)
                    if available_minutes <= 0:
                        continue
                    booked_minutes = sum(
                        _minutes_overlap(
                            a.starts_at, a.ends_at, bucket_start, bucket_start + timedelta(hours=1)
                        )
                        for a in Appointment.objects.filter(
                            clinic_id=clinic_id,
                            vet_id=vet.id,
                            status__in=ACTIVE_APPOINTMENT_STATUSES,
                            starts_at__lt=bucket_start + timedelta(hours=1),
                            ends_at__gt=bucket_start,
                        ).only("starts_at", "ends_at")
                    )
                    utilization_pct = round((booked_minutes / available_minutes) * 100, 2)
                    row = {
                        "vet_id": vet.id,
                        "vet_name": vet.get_full_name() or vet.username,
                        "bucket_start": bucket_start.isoformat(),
                        "bucket_end": (bucket_start + timedelta(hours=1)).isoformat(),
                        "available_minutes": available_minutes,
                        "booked_minutes": booked_minutes,
                        "utilization_pct": utilization_pct,
                        "is_overload": utilization_pct >= overload_threshold_pct,
                    }
                    rows.append(row)
                    if row["is_overload"]:
                        overload_windows.append(row)
            else:
                utilization_pct = (
                    round((booked_minutes_day / available_minutes_day) * 100, 2)
                    if available_minutes_day > 0
                    else 0.0
                )
                row = {
                    "vet_id": vet.id,
                    "vet_name": vet.get_full_name() or vet.username,
                    "day": day.isoformat(),
                    "available_minutes": available_minutes_day,
                    "booked_minutes": booked_minutes_day,
                    "utilization_pct": utilization_pct,
                    "is_overload": utilization_pct >= overload_threshold_pct
                    and available_minutes_day > 0,
                }
                rows.append(row)
                if row["is_overload"]:
                    overload_windows.append(row)

                day_key = day.isoformat()
                by_day.setdefault(
                    day_key,
                    {
                        "day": day_key,
                        "available_minutes": 0,
                        "booked_minutes": 0,
                        "utilization_pct": 0.0,
                    },
                )
                by_day[day_key]["available_minutes"] += available_minutes_day
                by_day[day_key]["booked_minutes"] += booked_minutes_day

            by_vet[vet.id]["available_minutes"] += available_minutes_day
            by_vet[vet.id]["booked_minutes"] += booked_minutes_day

    for vet_row in by_vet.values():
        available = vet_row["available_minutes"]
        booked = vet_row["booked_minutes"]
        vet_row["utilization_pct"] = round((booked / available) * 100, 2) if available > 0 else 0.0

    for day_row in by_day.values():
        available = day_row["available_minutes"]
        booked = day_row["booked_minutes"]
        day_row["utilization_pct"] = round((booked / available) * 100, 2) if available > 0 else 0.0

    total_available = sum(v["available_minutes"] for v in by_vet.values())
    total_booked = sum(v["booked_minutes"] for v in by_vet.values())
    total_utilization = (
        round((total_booked / total_available) * 100, 2) if total_available > 0 else 0.0
    )

    return {
        "kind": "scheduling_capacity_insights",
        "window": {"from": start_date.isoformat(), "to": end_date.isoformat()},
        "granularity": granularity,
        "overload_threshold_pct": overload_threshold_pct,
        "summary": {
            "available_minutes": total_available,
            "booked_minutes": total_booked,
            "utilization_pct": total_utilization,
            "overload_windows_count": len(overload_windows),
        },
        "by_vet": list(by_vet.values()),
        "by_day": list(by_day.values()),
        "rows": rows,
        "overload_windows": overload_windows,
        "generated_at": timezone.now().isoformat(),
    }


def _find_reassign_candidate(
    *,
    appointment: Appointment,
    clinic_id: int,
    day: date_type,
    vet_ids: list[int],
) -> dict[str, object] | None:
    for candidate_vet_id in vet_ids:
        if candidate_vet_id == appointment.vet_id:
            continue
        candidate_intervals = _get_vet_intervals(clinic_id, candidate_vet_id, day)
        if not any(
            it.start <= appointment.starts_at and it.end >= appointment.ends_at
            for it in candidate_intervals
        ):
            continue
        if _is_slot_free_for_appointment(
            clinic_id=clinic_id,
            vet_id=candidate_vet_id,
            room_id=appointment.room_id,
            start_at=appointment.starts_at,
            end_at=appointment.ends_at,
            exclude_appointment_id=appointment.id,
        ):
            return {
                "kind": "reassign_vet",
                "proposed_vet_id": candidate_vet_id,
                "proposed_starts_at": appointment.starts_at.isoformat(),
                "proposed_ends_at": appointment.ends_at.isoformat(),
            }
    return None


def _find_move_candidate(
    *, appointment: Appointment, clinic_id: int, day: date_type
) -> dict[str, object] | None:
    intervals = _get_vet_intervals(clinic_id, appointment.vet_id, day)
    duration = appointment.ends_at - appointment.starts_at
    step = timedelta(minutes=30)
    for interval in intervals:
        start_at = interval.start
        while start_at + duration <= interval.end:
            if start_at != appointment.starts_at and _is_slot_free_for_appointment(
                clinic_id=clinic_id,
                vet_id=appointment.vet_id,
                room_id=appointment.room_id,
                start_at=start_at,
                end_at=start_at + duration,
                exclude_appointment_id=appointment.id,
            ):
                return {
                    "kind": "move_slot",
                    "proposed_vet_id": appointment.vet_id,
                    "proposed_starts_at": start_at.isoformat(),
                    "proposed_ends_at": (start_at + duration).isoformat(),
                }
            start_at = start_at + step
    return None


def generate_optimization_suggestions(
    *,
    clinic_id: int,
    start_date: date_type,
    end_date: date_type,
    limit: int = 5,
    vet_id: int | None = None,
    overload_threshold_pct: float = 85.0,
) -> dict[str, object]:
    insights = generate_capacity_insights(
        clinic_id=clinic_id,
        start_date=start_date,
        end_date=end_date,
        granularity="day",
        vet_id=vet_id,
        overload_threshold_pct=overload_threshold_pct,
    )
    overloaded_rows = [row for row in insights["rows"] if row["is_overload"]]
    overloaded_rows.sort(key=lambda row: (-row["utilization_pct"], row["day"], row["vet_id"]))

    vet_ids = list(
        User.objects.filter(clinic_id=clinic_id, is_vet=True)
        .order_by("id")
        .values_list("id", flat=True)
    )
    suggestions: list[dict[str, object]] = []

    for row in overloaded_rows:
        day = date_type.fromisoformat(str(row["day"]))
        appointments = (
            Appointment.objects.filter(
                clinic_id=clinic_id,
                vet_id=row["vet_id"],
                status__in=ACTIVE_APPOINTMENT_STATUSES,
                starts_at__date=day,
            )
            .select_related("vet", "room")
            .order_by("-ends_at", "id")
        )
        for appt in appointments:
            duration_minutes = int((appt.ends_at - appt.starts_at).total_seconds() // 60)
            reassign = _find_reassign_candidate(
                appointment=appt,
                clinic_id=clinic_id,
                day=day,
                vet_ids=vet_ids,
            )
            suggestion_core = reassign or _find_move_candidate(
                appointment=appt, clinic_id=clinic_id, day=day
            )
            if not suggestion_core:
                continue

            proposed_vet = (
                User.objects.filter(id=suggestion_core["proposed_vet_id"])
                .only("id", "username", "first_name", "last_name")
                .first()
            )
            proposed_vet_name = (
                (proposed_vet.get_full_name() or proposed_vet.username) if proposed_vet else ""
            )
            reason = (
                "Reassign to a lower-load qualified vet in the same time window."
                if suggestion_core["kind"] == "reassign_vet"
                else "Move to a free slot to reduce overload for this vet/day."
            )
            suggestion_id = (
                f"{suggestion_core['kind']}:{appt.id}:{suggestion_core['proposed_vet_id']}:"
                f"{suggestion_core['proposed_starts_at']}"
            )
            suggestions.append(
                {
                    "id": suggestion_id,
                    "kind": suggestion_core["kind"],
                    "appointment_id": appt.id,
                    "impact_estimate": {
                        "minutes_shifted": duration_minutes,
                        "overload_reduction_pct": min(
                            100.0, round((duration_minutes / 60) * 12.5, 2)
                        ),
                    },
                    "reason": reason,
                    "confidence": 0.78 if suggestion_core["kind"] == "reassign_vet" else 0.71,
                    "current": {
                        "vet_id": appt.vet_id,
                        "vet_name": appt.vet.get_full_name() or appt.vet.username,
                        "starts_at": appt.starts_at.isoformat(),
                        "ends_at": appt.ends_at.isoformat(),
                        "room_id": appt.room_id,
                    },
                    "proposed": {
                        "vet_id": suggestion_core["proposed_vet_id"],
                        "vet_name": proposed_vet_name,
                        "starts_at": suggestion_core["proposed_starts_at"],
                        "ends_at": suggestion_core["proposed_ends_at"],
                        "room_id": appt.room_id,
                    },
                }
            )
            if len(suggestions) >= limit:
                break
        if len(suggestions) >= limit:
            break

    return {
        "kind": "scheduling_optimization_suggestions",
        "window": {"from": start_date.isoformat(), "to": end_date.isoformat()},
        "overload_threshold_pct": overload_threshold_pct,
        "count": len(suggestions),
        "suggestions": suggestions,
        "generated_at": timezone.now().isoformat(),
    }
