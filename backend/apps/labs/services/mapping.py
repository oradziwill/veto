from __future__ import annotations

from apps.labs.models import LabIntegrationDevice, LabTest, LabTestCodeMap


def resolve_internal_test(
    *,
    clinic_id: int,
    device: LabIntegrationDevice | None,
    vendor_code: str,
    species: str = "",
) -> LabTest | None:
    """Pick lab catalog test for a vendor code; device-specific maps beat global (device NULL)."""
    if not vendor_code:
        return None

    base_qs = LabTestCodeMap.objects.filter(
        clinic_id=clinic_id,
        vendor_code=vendor_code,
    ).select_related("lab_test")

    if species:
        qs = base_qs.filter(species__in=["", species]).order_by("-priority")
    else:
        qs = base_qs.filter(species="").order_by("-priority")

    if device and device.id:
        specific = qs.filter(device_id=device.id).first()
        if specific:
            return specific.lab_test

    global_map = qs.filter(device__isnull=True).first()
    return global_map.lab_test if global_map else None
