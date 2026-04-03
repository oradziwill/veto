from __future__ import annotations

from apps.labs.integrations.dto import IdentifierDraft
from apps.labs.models import LabExternalIdentifier, LabOrder, LabSample


def resolve_order_from_identifiers(
    clinic_id: int,
    identifiers: list[IdentifierDraft],
) -> tuple[LabOrder | None, LabSample | None]:
    """
    Resolve clinic LabOrder (+ optional LabSample) from inbound identifier list.
    Checks LabExternalIdentifier first, then LabOrder.external_accession_number.
    """
    for ident in identifiers:
        ext = (
            LabExternalIdentifier.objects.filter(
                clinic_id=clinic_id,
                scheme=ident.scheme,
                value=ident.value,
            )
            .select_related("sample__lab_order")
            .first()
        )
        if ext and ext.sample_id:
            return ext.sample.lab_order, ext.sample

    for ident in identifiers:
        order = LabOrder.objects.filter(
            clinic_id=clinic_id,
            external_accession_number=ident.value,
        ).first()
        if order:
            return order, None

    return None, None
