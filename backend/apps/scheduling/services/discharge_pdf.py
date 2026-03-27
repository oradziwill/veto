from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_lines(summary_data: dict[str, Any]) -> list[str]:
    lines: list[str] = ["Hospital Discharge Summary", ""]

    for key, label in (
        ("diagnosis", "Diagnosis"),
        ("hospitalization_course", "Hospitalization Course"),
        ("procedures", "Procedures"),
        ("home_care_instructions", "Home Care Instructions"),
        ("warning_signs", "Warning Signs"),
        ("follow_up_date", "Follow-up Date"),
        ("finalized_at", "Finalized At"),
    ):
        value = _format_value(summary_data.get(key))
        if value:
            lines.append(f"{label}: {value}")

    medications = summary_data.get("medications_on_discharge") or []
    lines.append("")
    lines.append("Medications on Discharge:")
    if not medications:
        lines.append("- none")
    else:
        for medication in medications:
            medication_name = _format_value(medication.get("medication_name", "")).strip()
            dose = _format_value(medication.get("dose", "")).strip()
            dose_unit = _format_value(medication.get("dose_unit", "")).strip()
            route = _format_value(medication.get("route", "")).strip()
            frequency_hours = _format_value(medication.get("frequency_hours", "")).strip()
            instructions = _format_value(medication.get("instructions", "")).strip()
            parts = [p for p in [medication_name, f"{dose} {dose_unit}".strip(), route] if p]
            line = "- " + " / ".join(parts)
            if frequency_hours:
                line += f" / every {frequency_hours}h"
            if instructions:
                line += f" ({instructions})"
            lines.append(line)

    return lines


def render_discharge_summary_pdf_bytes(summary_data: dict[str, Any]) -> bytes:
    """
    Render a simple, dependency-free single-page PDF document.
    This keeps backend deployment lightweight while still producing a real PDF.
    """
    lines = _build_lines(summary_data)[:55]
    content_stream_lines = ["BT", "/F1 11 Tf", "50 790 Td"]
    first_line = True
    for line in lines:
        escaped = _escape_pdf_text(line)
        if first_line:
            content_stream_lines.append(f"({escaped}) Tj")
            first_line = False
        else:
            content_stream_lines.append(f"0 -14 Td ({escaped}) Tj")
    content_stream_lines.append("ET")
    content_stream = "\n".join(content_stream_lines).encode("latin-1", errors="replace")

    objects = []
    objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    objects.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    objects.append(
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
    )
    objects.append(b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")
    objects.append(
        b"5 0 obj << /Length "
        + str(len(content_stream)).encode("ascii")
        + b" >> stream\n"
        + content_stream
        + b"\nendstream endobj\n"
    )

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_offset = len(pdf)
    pdf.extend(b"xref\n")
    pdf.extend(f"0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        b"trailer << /Size "
        + str(len(objects) + 1).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF"
    )
    return bytes(pdf)
