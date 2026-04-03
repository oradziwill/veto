from __future__ import annotations

from django.utils import timezone

from apps.labs.models import LabObservation, LabOrder, LabResult, LabResultComponent


def _apply_legacy_scalar_from_component(result: LabResult, comp: LabResultComponent) -> None:
    if comp.value_numeric is not None:
        result.value_numeric = comp.value_numeric
    if comp.value_text:
        result.value = comp.value_text
    elif comp.value_numeric is not None:
        result.value = str(comp.value_numeric)
    if comp.unit:
        result.unit = comp.unit
    if comp.ref_low or comp.ref_high:
        low, high = comp.ref_low, comp.ref_high
        result.reference_range = f"{low}-{high}" if low and high else (low or high or "")


def materialize_lab_order(order: LabOrder) -> None:
    """Promote matched observations on this order into LabResult + LabResultComponent rows."""
    for line in order.lines.select_related("result", "test").prefetch_related("result__components"):
        result = line.result
        observations = LabObservation.objects.filter(
            lab_order_line=line,
            internal_test=line.test,
            match_status=LabObservation.MatchStatus.MATCHED,
        ).order_by("id")

        for obs in observations:
            LabResultComponent.objects.update_or_create(
                lab_result=result,
                lab_test=line.test,
                defaults={
                    "clinic_id": order.clinic_id,
                    "source_observation": obs,
                    "value_text": obs.value_text,
                    "value_numeric": obs.value_numeric,
                    "unit": obs.unit,
                    "ref_low": obs.ref_low,
                    "ref_high": obs.ref_high,
                    "abnormal_flag": obs.abnormal_flag,
                    "sort_order": 0,
                },
            )

        if observations.exists():
            comp = result.components.filter(lab_test=line.test).first()
            if comp:
                _apply_legacy_scalar_from_component(result, comp)
            if result.source == LabResult.Source.MANUAL:
                result.source = LabResult.Source.MIXED
            else:
                result.source = LabResult.Source.INTEGRATION
            result.integration_updated_at = timezone.now()
            result.primary_observation_id = observations.last().id
            result.status = LabResult.Status.COMPLETED
            if not result.completed_at:
                result.completed_at = timezone.now()
            result.save(
                update_fields=[
                    "value",
                    "value_numeric",
                    "unit",
                    "reference_range",
                    "source",
                    "integration_updated_at",
                    "primary_observation",
                    "status",
                    "completed_at",
                ]
            )


def refresh_order_status_after_integration(order: LabOrder) -> None:
    """Set partial_result / completed when components exist on line results."""
    lines = list(order.lines.select_related("result").prefetch_related("result__components"))
    if not lines:
        return
    any_comp = any(line.result.components.exists() for line in lines)
    all_comp = all(line.result.components.exists() for line in lines)
    if all_comp:
        order.status = LabOrder.Status.COMPLETED
        if not order.completed_at:
            order.completed_at = timezone.now()
    elif any_comp:
        order.status = LabOrder.Status.PARTIAL_RESULT
    if any_comp:
        order.save(update_fields=["status", "completed_at"])
