from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsStaffOrVet
from apps.scheduling.services.scheduling_assistant import (
    generate_capacity_insights,
    generate_optimization_suggestions,
)


def _parse_window(request):
    today = timezone.localdate()
    from_str = request.query_params.get("from", "")
    to_str = request.query_params.get("to", "")

    if not from_str and not to_str:
        start_date = today
        end_date = today + timedelta(days=13)
        return start_date, end_date, None

    start_date = parse_date(from_str) if from_str else None
    end_date = parse_date(to_str) if to_str else None
    if start_date is None or end_date is None:
        return None, None, "Invalid date range. Use from/to in YYYY-MM-DD format."
    if end_date < start_date:
        return None, None, "`to` must be the same day or after `from`."
    if (end_date - start_date).days > 60:
        return None, None, "Date range cannot exceed 60 days."
    return start_date, end_date, None


class SchedulingCapacityInsightsView(APIView):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get(self, request):
        start_date, end_date, window_error = _parse_window(request)
        if window_error:
            return Response({"detail": window_error}, status=400)

        granularity = request.query_params.get("granularity", "day").strip().lower()
        if granularity not in {"day", "hour"}:
            return Response({"detail": "granularity must be one of: day, hour."}, status=400)

        vet_str = request.query_params.get("vet", "").strip()
        vet_id = int(vet_str) if vet_str.isdigit() else None
        threshold_str = request.query_params.get("overload_threshold_pct", "").strip()
        try:
            overload_threshold_pct = float(threshold_str) if threshold_str else 85.0
        except ValueError:
            return Response({"detail": "overload_threshold_pct must be a number."}, status=400)
        overload_threshold_pct = max(1.0, min(100.0, overload_threshold_pct))

        payload = generate_capacity_insights(
            clinic_id=request.user.clinic_id,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            vet_id=vet_id,
            overload_threshold_pct=overload_threshold_pct,
        )
        return Response(payload, status=200)


class SchedulingOptimizationSuggestionsView(APIView):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get(self, request):
        start_date, end_date, window_error = _parse_window(request)
        if window_error:
            return Response({"detail": window_error}, status=400)

        vet_str = request.query_params.get("vet", "").strip()
        vet_id = int(vet_str) if vet_str.isdigit() else None
        limit_str = request.query_params.get("limit", "").strip()
        limit = int(limit_str) if limit_str.isdigit() else 5
        limit = max(1, min(20, limit))

        threshold_str = request.query_params.get("overload_threshold_pct", "").strip()
        try:
            overload_threshold_pct = float(threshold_str) if threshold_str else 85.0
        except ValueError:
            return Response({"detail": "overload_threshold_pct must be a number."}, status=400)
        overload_threshold_pct = max(1.0, min(100.0, overload_threshold_pct))

        payload = generate_optimization_suggestions(
            clinic_id=request.user.clinic_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            vet_id=vet_id,
            overload_threshold_pct=overload_threshold_pct,
        )
        return Response(payload, status=200)
