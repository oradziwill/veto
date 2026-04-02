from __future__ import annotations

import base64
import hashlib
import html
import json
from typing import Any

import fitz

from apps.scheduling.models import Appointment


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_content_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def build_payload(appointment: Appointment) -> dict[str, Any]:
    """Snapshot fields for consent PDF and tamper-evident hash."""
    patient = appointment.patient
    owner = patient.owner
    vet = appointment.vet
    clinic = appointment.clinic
    owner_name = f"{owner.first_name} {owner.last_name}".strip()
    vet_name = ""
    if vet:
        vet_name = f"{vet.first_name or ''} {vet.last_name or ''}".strip() or (vet.username or "")
    starts = appointment.starts_at
    return {
        "template_version": "1",
        "document_type": "procedure_consent",
        "clinic_name": clinic.name,
        "appointment_id": appointment.id,
        "appointment_starts_at": starts.isoformat() if starts else "",
        "patient_name": patient.name,
        "patient_species": patient.species or "",
        "owner_full_name": owner_name,
        "reason": (appointment.reason or "").strip(),
        "vet_name": vet_name,
    }


def _html_payload(payload: dict[str, Any], signature_png_bytes: bytes | None) -> str:
    def esc(x: Any) -> str:
        return html.escape(str(x), quote=True)

    sig_b64 = base64.b64encode(signature_png_bytes).decode("ascii") if signature_png_bytes else None

    body = [
        "<h2 style='margin-top:0'>Zgoda na zabieg</h2>",
        f"<p><b>Klinika:</b> {esc(payload.get('clinic_name', ''))}</p>",
        f"<p><b>Data wizyty:</b> {esc(payload.get('appointment_starts_at', ''))}</p>",
        f"<p><b>Pacjent:</b> {esc(payload.get('patient_name', ''))} ({esc(payload.get('patient_species', ''))})</p>",
        f"<p><b>Właściciel:</b> {esc(payload.get('owner_full_name', ''))}</p>",
        f"<p><b>Planowany zabieg / powód:</b> {esc(payload.get('reason', ''))}</p>",
        f"<p><b>Lekarz prowadzący:</b> {esc(payload.get('vet_name', ''))}</p>",
        "<hr/>",
        "<p>Treść zgody: potwierdzam zapoznanie się z zakresem i charakterem planowego zabiegu oraz akceptuję "
        "proponowany plan postępowania.</p>",
    ]
    if sig_b64:
        body.append("<p><b>Podpis właściciela</b></p>")
        body.append(
            f'<p><img src="data:image/png;base64,{sig_b64}" style="max-width:480px;height:auto" alt="Podpis"/></p>'
        )
    else:
        body.append("<p><b>Podpis właściciela</b> (poniżej)</p>")
        body.append(
            '<div style="border:1px solid #333;height:140px;width:100%;max-width:480px"></div>'
        )

    return (
        '<html><body style="font-family:sans-serif;font-size:11pt;line-height:1.4">'
        + "".join(body)
        + "</body></html>"
    )


def render_consent_pdf_bytes(
    payload: dict[str, Any],
    signature_png_bytes: bytes | None,
) -> bytes:
    """A4 PDF; optional owner signature image embedded as PNG."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    html_str = _html_payload(payload, signature_png_bytes)
    page.insert_htmlbox(fitz.Rect(40, 40, 555, 802), html_str)
    out = doc.tobytes()
    doc.close()
    return out
