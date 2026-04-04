"""
Compact JSON-safe snapshots for audit log before/after payloads.
"""

from __future__ import annotations

from decimal import Decimal

from apps.billing.models import Invoice
from apps.clients.models import Client, ClientClinic
from apps.patients.models import Patient


def client_snapshot(client: Client) -> dict:
    return {
        "first_name": client.first_name,
        "last_name": client.last_name,
        "email": client.email or "",
        "phone": client.phone or "",
    }


def client_membership_snapshot(m: ClientClinic) -> dict:
    return {
        "client_id": m.client_id,
        "clinic_id": m.clinic_id,
        "is_active": m.is_active,
        "notes": (m.notes or "")[:500],
    }


def patient_snapshot(patient: Patient) -> dict:
    return {
        "name": patient.name,
        "species": patient.species,
        "owner_id": patient.owner_id,
        "microchip_no": patient.microchip_no or "",
        "primary_vet_id": patient.primary_vet_id,
    }


def invoice_audit_payload(invoice: Invoice) -> dict:
    lines = list(invoice.lines.all())
    total = sum((line.line_total for line in lines), Decimal("0"))
    return {
        "invoice_number": invoice.invoice_number or "",
        "status": invoice.status,
        "client_id": invoice.client_id,
        "patient_id": invoice.patient_id,
        "line_count": len(lines),
        "total_net": str(total.quantize(Decimal("0.01"))),
        "ksef_status": invoice.ksef_status or "",
    }
