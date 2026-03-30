"""
Assemble a clinic-scoped JSON bundle for a client (owner) — GDPR / access request.
Excludes internal-only fields (e.g. staff notes, AI cache).
"""

from __future__ import annotations

from django.utils import timezone

from apps.billing.models import Invoice
from apps.clients.models import Client, ClientClinic
from apps.medical.models import Vaccination
from apps.patients.models import Patient
from apps.scheduling.models import Appointment


def _gdpr_serialize_row(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if v is not None and hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def build_client_gdpr_export(*, client_id: int, clinic_id: int) -> dict | None:
    if not ClientClinic.objects.filter(
        client_id=client_id, clinic_id=clinic_id, is_active=True
    ).exists():
        return None

    client = Client.objects.filter(pk=client_id).first()
    if not client:
        return None

    m = ClientClinic.objects.filter(client_id=client_id, clinic_id=clinic_id).first()

    patients = Patient.objects.filter(owner_id=client_id, clinic_id=clinic_id).order_by("id")
    patient_ids = list(patients.values_list("id", flat=True))

    appts = (
        Appointment.objects.filter(patient_id__in=patient_ids, clinic_id=clinic_id)
        .order_by("-starts_at")[:500]
        .values(
            "id",
            "patient_id",
            "starts_at",
            "ends_at",
            "status",
            "visit_type",
            "reason",
            "vet_id",
            "booked_via_portal",
            "cancelled_at",
            "cancellation_reason",
        )
    )

    invs = (
        Invoice.objects.filter(client_id=client_id, clinic_id=clinic_id)
        .order_by("-created_at")[:200]
        .prefetch_related("lines")
    )
    invoices_out = []
    for inv in invs:
        lines = []
        for line in inv.lines.all():
            lines.append(
                {
                    "description": line.description,
                    "quantity": str(line.quantity),
                    "unit_price": str(line.unit_price),
                    "vat_rate": line.vat_rate,
                    "line_total": str(line.line_total),
                    "line_gross": str(line.line_gross),
                }
            )
        invoices_out.append(
            {
                "id": inv.id,
                "status": inv.status,
                "currency": inv.currency,
                "invoice_number": inv.invoice_number,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "created_at": inv.created_at.isoformat(),
                "total_net": str(inv.total),
                "total_gross": str(inv.total_gross),
                "lines": lines,
            }
        )

    vax = (
        Vaccination.objects.filter(patient_id__in=patient_ids, clinic_id=clinic_id)
        .order_by("-administered_at")[:200]
        .values(
            "id",
            "patient_id",
            "vaccine_name",
            "batch_number",
            "administered_at",
            "next_due_at",
            "notes",
        )
    )

    return {
        "export_generated_at": timezone.now().isoformat(),
        "clinic_id": clinic_id,
        "client": {
            "id": client.id,
            "first_name": client.first_name,
            "last_name": client.last_name,
            "email": client.email,
            "phone": client.phone,
            "nip": client.nip,
            "street": client.street,
            "house_number": client.house_number,
            "apartment": client.apartment,
            "city": client.city,
            "postal_code": client.postal_code,
            "country": client.country,
            "created_at": client.created_at.isoformat(),
        },
        "membership": (
            {
                "is_active": m.is_active,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            if m
            else None
        ),
        "patients": [
            {
                "id": p.id,
                "name": p.name,
                "species": p.species,
                "breed": p.breed,
                "sex": p.sex,
                "birth_date": p.birth_date.isoformat() if p.birth_date else None,
                "microchip_no": p.microchip_no,
                "allergies": p.allergies,
                "primary_vet_id": p.primary_vet_id,
                "created_at": p.created_at.isoformat(),
            }
            for p in patients
        ],
        "appointments": [_gdpr_serialize_row(dict(row)) for row in appts],
        "invoices": invoices_out,
        "vaccinations": [_gdpr_serialize_row(dict(row)) for row in vax],
        "_note": "Internal staff notes and AI fields on patients are omitted.",
    }
