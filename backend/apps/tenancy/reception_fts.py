"""
PostgreSQL full-text search for reception client/patient lists.

When ``connection.vendor != "postgresql"``, falls back to the previous
icontains-based filters so local SQLite tests keep working.
"""

from __future__ import annotations

from django.db import connection
from django.db.models import Q, QuerySet


def _is_postgresql() -> bool:
    return connection.vendor == "postgresql"


def filter_clients_queryset_for_reception(qs: QuerySet, q: str) -> QuerySet:
    """Apply text search for :class:`~apps.clients.models.Client` list (param ``q``)."""
    q = q.strip()
    parts = q.split()
    legacy = (
        Q(first_name__icontains=q)
        | Q(last_name__icontains=q)
        | Q(phone__icontains=q)
        | Q(email__icontains=q)
    )
    if len(parts) >= 2:
        legacy |= Q(first_name__icontains=parts[0], last_name__icontains=" ".join(parts[1:]))
        legacy |= Q(first_name__icontains=" ".join(parts[1:]), last_name__icontains=parts[0])

    if not _is_postgresql():
        return qs.filter(legacy)

    from django.contrib.postgres.search import SearchQuery, SearchVector

    vector = (
        SearchVector("first_name", config="simple", weight="A")
        + SearchVector("last_name", config="simple", weight="A")
        + SearchVector("phone", config="simple", weight="B")
        + SearchVector("email", config="simple", weight="B")
    )
    fts_query = SearchQuery(q, config="simple")
    return qs.annotate(_reception_fts=vector).filter(Q(_reception_fts=fts_query) | legacy)


def filter_patients_queryset_for_reception(qs: QuerySet, search: str) -> QuerySet:
    """Apply text search for :class:`~apps.patients.models.Patient` list (param ``search``)."""
    search = search.strip()
    legacy = (
        Q(name__icontains=search)
        | Q(microchip_no__icontains=search)
        | Q(owner__first_name__icontains=search)
        | Q(owner__last_name__icontains=search)
        | Q(owner__phone__icontains=search)
    )

    if not _is_postgresql():
        return qs.filter(legacy)

    from django.contrib.postgres.search import SearchQuery, SearchVector

    vector = (
        SearchVector("name", config="simple", weight="A")
        + SearchVector("microchip_no", config="simple", weight="A")
        + SearchVector("species", config="simple", weight="C")
        + SearchVector("breed", config="simple", weight="C")
        + SearchVector("owner__first_name", config="simple", weight="B")
        + SearchVector("owner__last_name", config="simple", weight="B")
        + SearchVector("owner__phone", config="simple", weight="B")
        + SearchVector("owner__email", config="simple", weight="C")
    )
    fts_query = SearchQuery(search, config="simple")
    return qs.annotate(_reception_fts=vector).filter(Q(_reception_fts=fts_query) | legacy)
