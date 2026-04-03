"""
Clinic access helpers for staff and network-level users.

Use :func:`accessible_clinic_ids` in querysets (``clinic_id__in=...``).
Use :func:`clinic_id_for_mutation` when creating or updating rows that require a single clinic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.exceptions import PermissionDenied, ValidationError

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser


def accessible_clinic_ids(user: AbstractBaseUser | None) -> list[int]:
    """
    Return clinic primary keys the user may access.

    - Superuser: all clinics.
    - Network admin: all clinics in ``user.network``.
    - Everyone else: at most ``[user.clinic_id]`` when set.
    """
    if not user or not user.is_authenticated:
        return []
    if getattr(user, "is_superuser", False):
        from apps.tenancy.models import Clinic

        return list(Clinic.objects.order_by().values_list("id", flat=True))

    role = getattr(user, "role", None)
    if role == "network_admin":
        nid = getattr(user, "network_id", None)
        if not nid:
            return []
        from apps.tenancy.models import Clinic

        return list(Clinic.objects.filter(network_id=nid).order_by().values_list("id", flat=True))

    cid = getattr(user, "clinic_id", None)
    if cid:
        return [cid]
    return []


def clinic_id_for_mutation(
    user,
    *,
    request,
    instance_clinic_id: int | None = None,
) -> int:
    """
    Resolve the clinic id for a create/update when the model has a single ``clinic`` FK.

    If the user has access to exactly one clinic, that id is used.
    If the user spans multiple clinics (network admin), ``clinic_id`` must be present
    on the query string or in the request body.
    If ``instance_clinic_id`` is provided (e.g. updating an existing row), it must lie
    in :func:`accessible_clinic_ids` and is returned.
    """
    ids = accessible_clinic_ids(user)
    if not ids:
        raise ValidationError("No clinic access for this account.")
    allowed = set(ids)
    if instance_clinic_id is not None:
        if instance_clinic_id not in allowed:
            raise PermissionDenied("You do not have access to this clinic.")
        return instance_clinic_id
    if len(ids) == 1:
        return ids[0]

    raw = None
    if request is not None:
        raw = request.query_params.get("clinic_id")
        if raw is None and hasattr(request, "data"):
            raw = request.data.get("clinic_id")
    if raw is None:
        raise ValidationError(
            {"clinic_id": "This field is required when your account spans multiple clinics."}
        )
    try:
        cid = int(raw)
    except (TypeError, ValueError) as err:
        raise ValidationError({"clinic_id": "Invalid clinic id."}) from err
    if cid not in allowed:
        raise PermissionDenied("You do not have access to this clinic.")
    return cid
