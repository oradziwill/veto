"""
Clinic access helpers for staff and network-level users.

Use :func:`accessible_clinic_ids` in querysets (``clinic_id__in=...``).
Use :func:`clinic_id_for_mutation` when creating or updating rows that require a single clinic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import PermissionDenied, ValidationError

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

SUPERUSER_CLINIC_IDS_CACHE_KEY = "tenancy:superuser_clinic_ids"


def network_clinic_ids_cache_key(network_id: int) -> str:
    return f"tenancy:network_clinic_ids:{network_id}"


def _accessible_clinic_ids_cache_timeout() -> int:
    return int(getattr(settings, "ACCESSIBLE_CLINIC_IDS_CACHE_TIMEOUT", 300))


def _all_clinic_ids_for_superuser() -> list[int]:
    cached = cache.get(SUPERUSER_CLINIC_IDS_CACHE_KEY)
    if cached is not None:
        return list(cached)
    from apps.tenancy.models import Clinic

    ids = list(Clinic.objects.order_by().values_list("id", flat=True))
    cache.set(
        SUPERUSER_CLINIC_IDS_CACHE_KEY,
        ids,
        _accessible_clinic_ids_cache_timeout(),
    )
    return ids


def _clinic_ids_for_network(network_id: int) -> list[int]:
    key = network_clinic_ids_cache_key(network_id)
    cached = cache.get(key)
    if cached is not None:
        return list(cached)
    from apps.tenancy.models import Clinic

    ids = list(Clinic.objects.filter(network_id=network_id).order_by().values_list("id", flat=True))
    cache.set(key, ids, _accessible_clinic_ids_cache_timeout())
    return ids


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
        return _all_clinic_ids_for_superuser()

    role = getattr(user, "role", None)
    if role == "network_admin":
        nid = getattr(user, "network_id", None)
        if not nid:
            return []
        return _clinic_ids_for_network(int(nid))

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


def user_can_access_clinic(user, clinic_id: int | None) -> bool:
    """True if ``clinic_id`` is in :func:`accessible_clinic_ids`."""
    if clinic_id is None:
        return False
    return clinic_id in accessible_clinic_ids(user)


def clinic_instance_for_mutation(user, request, *, instance_clinic_id: int | None = None):
    """Resolve :class:`~apps.tenancy.models.Clinic` for serializer.save(clinic=...)."""
    from apps.tenancy.models import Clinic

    pk = clinic_id_for_mutation(user, request=request, instance_clinic_id=instance_clinic_id)
    return Clinic.objects.get(pk=pk)
