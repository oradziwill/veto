"""
Intelligent schedule generator.

Algorithm:
  For each clinic-open day in the requested range:
    1. Skip clinic holidays.
    2. Split the day into shifts based on clinic_wh.shift_hours.
       (If shift_hours is null, the whole open period is one shift.)
    3. For each shift, find available doctors:
       - Not on PTO for that date.
       - Either has VetWorkingHours for that weekday (active), OR has no schedule at all
         (assume always available).
       - Not already assigned to an earlier shift the same day.
    4. Among available doctors, pick the one with the fewest assignments so far
       to ensure fair rotation.
    5. Use doctor's specific hours for time bounds if set, otherwise use the shift window.
    6. Write DutyAssignment records (skip day if overwrite=False and day already covered).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from apps.scheduling.models_clinic_hours import ClinicWorkingHours
from apps.scheduling.models_duty import DutyAssignment
from apps.scheduling.models_exceptions import VetAvailabilityException
from apps.scheduling.models_working_hours import VetWorkingHours
from apps.tenancy.models import Clinic, ClinicHoliday
from django.db import transaction
from django.db.models import Count


def _build_shifts(clinic_wh: ClinicWorkingHours) -> list[tuple[time, time]]:
    """
    Split a clinic open period into a list of (start, end) time tuples.
    If shift_hours is None, returns a single shift covering the full open period.
    """
    if not clinic_wh.shift_hours:
        return [(clinic_wh.start_time, clinic_wh.end_time)]

    base = date.today()
    start_dt = datetime.combine(base, clinic_wh.start_time)
    end_dt = datetime.combine(base, clinic_wh.end_time)
    delta = timedelta(hours=clinic_wh.shift_hours)

    shifts = []
    cursor = start_dt
    while cursor < end_dt:
        shift_end = min(cursor + delta, end_dt)
        shifts.append((cursor.time(), shift_end.time()))
        cursor = shift_end
    return shifts


def generate_schedule(
    clinic: Clinic,
    start_date: date,
    end_date: date,
    doctors,  # QuerySet[User]
    overwrite: bool = False,
) -> dict:
    """
    Generate duty assignments for a date range.
    Returns a summary dict with created/skipped counts and any warnings.
    """

    # Pre-load clinic open days
    clinic_hours: dict[int, ClinicWorkingHours] = {
        wh.weekday: wh
        for wh in ClinicWorkingHours.objects.filter(clinic=clinic, is_active=True)
    }

    # Pre-load clinic holidays in range
    holiday_dates: set[date] = set(
        ClinicHoliday.objects.filter(
            clinic=clinic, is_active=True, date__gte=start_date, date__lte=end_date
        ).values_list("date", flat=True)
    )

    # Pre-load PTO (day-off exceptions) per doctor in range
    pto_by_vet: dict[int, set[date]] = {doc.id: set() for doc in doctors}
    for exc in VetAvailabilityException.objects.filter(
        clinic=clinic,
        is_day_off=True,
        date__gte=start_date,
        date__lte=end_date,
        vet__in=[d.id for d in doctors],
    ):
        pto_by_vet.setdefault(exc.vet_id, set()).add(exc.date)

    # Pre-load working hours per doctor (weekday → VetWorkingHours)
    wh_by_vet: dict[int, dict[int, VetWorkingHours]] = {doc.id: {} for doc in doctors}
    for wh in VetWorkingHours.objects.filter(
        vet__in=[d.id for d in doctors], is_active=True
    ):
        wh_by_vet[wh.vet_id][wh.weekday] = wh

    # Track existing assignments to avoid overwriting (keyed by date)
    existing_dates: set[date] = set()
    if not overwrite:
        existing_dates = set(
            DutyAssignment.objects.filter(
                clinic=clinic, date__gte=start_date, date__lte=end_date
            ).values_list("date", flat=True)
        )

    # Fair rotation: seed counts from ALL existing assignments so global fairness holds
    assignment_counts: dict[int, int] = {doc.id: 0 for doc in doctors}
    for row in (
        DutyAssignment.objects.filter(clinic=clinic)
        .values("vet_id")
        .annotate(cnt=Count("id"))
    ):
        if row["vet_id"] in assignment_counts:
            assignment_counts[row["vet_id"]] += row["cnt"]

    doctor_list = list(doctors)
    warnings: list[str] = []
    created = 0
    skipped_existing = 0
    skipped_no_doctors = 0
    skipped_closed = 0

    new_assignments: list[DutyAssignment] = []

    current = start_date
    while current <= end_date:
        # 1. Skip holidays
        if current in holiday_dates:
            current += timedelta(days=1)
            continue

        # 2. Check clinic open
        weekday = current.weekday()  # Mon=0 … Sun=6
        if weekday not in clinic_hours:
            skipped_closed += 1
            current += timedelta(days=1)
            continue

        clinic_wh = clinic_hours[weekday]

        # 3. Skip if already assigned (unless overwrite)
        if current in existing_dates:
            skipped_existing += 1
            current += timedelta(days=1)
            continue

        # 4. Split into shifts and assign a doctor to each
        shifts = _build_shifts(clinic_wh)
        assigned_today: set[int] = set()  # vet IDs already assigned today
        day_covered = False
        day_missing = False

        for shift_start, shift_end in shifts:
            # Find available doctors for this shift
            available = []
            for doc in doctor_list:
                if doc.id in assigned_today:
                    continue  # already doing another shift today
                if current in pto_by_vet.get(doc.id, set()):
                    continue  # on leave
                doc_wh = wh_by_vet.get(doc.id, {})
                if doc_wh:
                    # Explicit schedule: must have this weekday active
                    if weekday in doc_wh:
                        available.append(doc)
                else:
                    # No schedule defined → assume always available
                    available.append(doc)

            if not available:
                day_missing = True
                continue  # leave this shift uncovered

            # Pick doctor with fewest total assignments (fair rotation)
            available.sort(key=lambda d: assignment_counts[d.id])
            chosen = available[0]

            # Determine actual hours for this doctor
            doc_wh = wh_by_vet.get(chosen.id, {})
            if weekday in doc_wh:
                # Intersect doctor's hours with the shift window
                doc_start = max(doc_wh[weekday].start_time, shift_start)
                doc_end = min(doc_wh[weekday].end_time, shift_end)
                if doc_end <= doc_start:
                    # Doctor's hours don't overlap this shift — use shift window
                    doc_start, doc_end = shift_start, shift_end
                start_t, end_t = doc_start, doc_end
            else:
                start_t, end_t = shift_start, shift_end

            new_assignments.append(
                DutyAssignment(
                    clinic=clinic,
                    vet=chosen,
                    date=current,
                    start_time=start_t,
                    end_time=end_t,
                    is_auto_generated=True,
                )
            )
            assignment_counts[chosen.id] += 1
            assigned_today.add(chosen.id)
            day_covered = True
            created += 1

        if day_missing and not day_covered:
            skipped_no_doctors += 1
            warnings.append(str(current))
        elif day_missing:
            # Partially covered: add to warnings but don't count as fully uncovered
            warnings.append(f"{current} (partial)")

        current += timedelta(days=1)

    with transaction.atomic():
        if overwrite:
            DutyAssignment.objects.filter(
                clinic=clinic,
                date__gte=start_date,
                date__lte=end_date,
                is_auto_generated=True,
            ).delete()
        DutyAssignment.objects.bulk_create(new_assignments)

    return {
        "created": created,
        "skipped_existing": skipped_existing,
        "skipped_closed": skipped_closed,
        "skipped_no_doctors": skipped_no_doctors,
        "uncovered_dates": warnings,
    }
