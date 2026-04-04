from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import HasClinic, IsStaffOrVet
from apps.scheduling.services.scheduling_assistant import (
    generate_capacity_insights,
    generate_optimization_suggestions,
)
from apps.tenancy.access import accessible_clinic_ids, clinic_id_for_mutation
from apps.tenancy.models import Clinic

logger = logging.getLogger(__name__)
DEFAULT_WINDOW_DAYS = 14
MAX_WINDOW_DAYS = 60
MAX_HOURLY_WINDOW_DAYS = 14
DEFAULT_CAPACITY_ROWS_LIMIT = 1000
MAX_CAPACITY_ROWS_LIMIT = 5000
DEFAULT_SUGGESTIONS_LIMIT = 5
MAX_SUGGESTIONS_LIMIT = 20


def _parse_window(request):
    today = timezone.localdate()
    from_str = request.query_params.get("from", "")
    to_str = request.query_params.get("to", "")

    if not from_str and not to_str:
        start_date = today
        end_date = today + timedelta(days=DEFAULT_WINDOW_DAYS - 1)
        return start_date, end_date, None

    start_date = parse_date(from_str) if from_str else None
    end_date = parse_date(to_str) if to_str else None
    if start_date is None or end_date is None:
        return None, None, "Invalid date range. Use from/to in YYYY-MM-DD format."
    if end_date < start_date:
        return None, None, "`to` must be the same day or after `from`."
    if (end_date - start_date).days > MAX_WINDOW_DAYS:
        return None, None, f"Date range cannot exceed {MAX_WINDOW_DAYS} days."
    return start_date, end_date, None


def _parse_vet_id(request, user):
    ids = accessible_clinic_ids(user)
    if not ids:
        return None, "No clinic access."
    vet_str = request.query_params.get("vet", "").strip()
    if not vet_str:
        return None, None
    if not vet_str.isdigit():
        return None, "vet must be a numeric user ID."
    vet_id = int(vet_str)
    exists = User.objects.filter(clinic_id__in=ids, id=vet_id, is_vet=True).exists()
    if not exists:
        return None, "vet must reference an active clinic vet."
    return vet_id, None


def _parse_threshold(request):
    threshold_str = request.query_params.get("overload_threshold_pct", "").strip()
    try:
        value = float(threshold_str) if threshold_str else 85.0
    except ValueError:
        return None, "overload_threshold_pct must be a number."
    if value < 1.0 or value > 100.0:
        return None, "overload_threshold_pct must be between 1 and 100."
    return value, None


def _parse_rows_limit(request):
    rows_limit_str = request.query_params.get("rows_limit", "").strip()
    if not rows_limit_str:
        return DEFAULT_CAPACITY_ROWS_LIMIT, None
    if not rows_limit_str.isdigit():
        return None, "rows_limit must be an integer."
    rows_limit = int(rows_limit_str)
    if rows_limit < 1 or rows_limit > MAX_CAPACITY_ROWS_LIMIT:
        return None, f"rows_limit must be between 1 and {MAX_CAPACITY_ROWS_LIMIT}."
    return rows_limit, None


class SchedulingCapacityInsightsView(APIView):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get(self, request):
        cid = clinic_id_for_mutation(request.user, request=request, instance_clinic_id=None)
        if not Clinic.objects.filter(pk=cid, feature_ai_enabled=True).exists():
            return Response(
                {"detail": "Scheduling assistant is disabled for this clinic."},
                status=403,
            )

        start_date, end_date, window_error = _parse_window(request)
        if window_error:
            return Response({"detail": window_error}, status=400)

        granularity = request.query_params.get("granularity", "day").strip().lower()
        if granularity not in {"day", "hour"}:
            return Response({"detail": "granularity must be one of: day, hour."}, status=400)
        if granularity == "hour" and (end_date - start_date).days > MAX_HOURLY_WINDOW_DAYS:
            return Response(
                {
                    "detail": (
                        f"Hourly granularity supports a maximum window of "
                        f"{MAX_HOURLY_WINDOW_DAYS + 1} days."
                    )
                },
                status=400,
            )

        vet_id, vet_error = _parse_vet_id(request, request.user)
        if vet_error:
            return Response({"detail": vet_error}, status=400)
        overload_threshold_pct, threshold_error = _parse_threshold(request)
        if threshold_error:
            return Response({"detail": threshold_error}, status=400)
        rows_limit, rows_limit_error = _parse_rows_limit(request)
        if rows_limit_error:
            return Response({"detail": rows_limit_error}, status=400)

        try:
            payload = generate_capacity_insights(
                clinic_id=cid,
                start_date=start_date,
                end_date=end_date,
                granularity=granularity,
                vet_id=vet_id,
                overload_threshold_pct=overload_threshold_pct,
            )
        except Exception:
            logger.exception("Failed to generate scheduling capacity insights")
            return Response(
                {"detail": "Failed to generate capacity insights."},
                status=500,
            )

        rows = payload.get("rows", [])
        overload_windows = payload.get("overload_windows", [])
        if isinstance(rows, list) and len(rows) > rows_limit:
            payload["rows"] = rows[:rows_limit]
        if isinstance(overload_windows, list) and len(overload_windows) > rows_limit:
            payload["overload_windows"] = overload_windows[:rows_limit]
        payload["meta"] = {
            "rows_limit": rows_limit,
            "rows_truncated": isinstance(rows, list) and len(rows) > rows_limit,
            "overload_windows_truncated": (
                isinstance(overload_windows, list) and len(overload_windows) > rows_limit
            ),
            "applied_filters": {
                "from": start_date.isoformat(),
                "to": end_date.isoformat(),
                "granularity": granularity,
                "vet": vet_id,
                "overload_threshold_pct": overload_threshold_pct,
            },
        }
        return Response(payload, status=200)


class SchedulingOptimizationSuggestionsView(APIView):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get(self, request):
        cid = clinic_id_for_mutation(request.user, request=request, instance_clinic_id=None)
        if not Clinic.objects.filter(pk=cid, feature_ai_enabled=True).exists():
            return Response(
                {"detail": "Scheduling assistant is disabled for this clinic."},
                status=403,
            )

        start_date, end_date, window_error = _parse_window(request)
        if window_error:
            return Response({"detail": window_error}, status=400)

        vet_id, vet_error = _parse_vet_id(request, request.user)
        if vet_error:
            return Response({"detail": vet_error}, status=400)

        limit_str = request.query_params.get("limit", "").strip()
        if not limit_str:
            limit = DEFAULT_SUGGESTIONS_LIMIT
        elif not limit_str.isdigit():
            return Response({"detail": "limit must be an integer."}, status=400)
        else:
            limit = int(limit_str)
            if limit < 1 or limit > MAX_SUGGESTIONS_LIMIT:
                return Response(
                    {"detail": f"limit must be between 1 and {MAX_SUGGESTIONS_LIMIT}."},
                    status=400,
                )

        overload_threshold_pct, threshold_error = _parse_threshold(request)
        if threshold_error:
            return Response({"detail": threshold_error}, status=400)

        try:
            payload = generate_optimization_suggestions(
                clinic_id=cid,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                vet_id=vet_id,
                overload_threshold_pct=overload_threshold_pct,
            )
        except Exception:
            logger.exception("Failed to generate scheduling optimization suggestions")
            return Response(
                {"detail": "Failed to generate optimization suggestions."},
                status=500,
            )

        return Response(payload, status=200)
