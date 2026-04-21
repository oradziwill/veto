from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

SB, EB, CR = b"\x0b", b"\x1c", b"\x0d"


def wrap_mllp(payload: bytes) -> bytes:
    return SB + payload + EB + CR


def extract_mllp_frames(buf: bytearray) -> list[bytes]:
    """Remove complete MLLP frames from buf (mutates buf), return payloads (no SB/EB/CR)."""
    out: list[bytes] = []
    while True:
        start = buf.find(SB)
        if start == -1:
            break
        if start > 0:
            del buf[:start]
        end = buf.find(EB + CR, 0)
        if end == -1:
            break
        inner = bytes(buf[1:end])
        del buf[: end + 2]
        out.append(inner)
    return out


def _split_fields(segment: str) -> list[str]:
    return segment.split("|")


def _first_component(ce: str) -> str:
    if not ce:
        return ""
    return ce.split("^", 1)[0].strip()


def _parse_ref_range(obx7: str) -> tuple[str, str]:
    if not obx7 or obx7 == "-":
        return "", ""
    # e.g. 6.00-17.00 or 6.00 - 17.00
    m = re.match(r"^\s*([\d.]+)\s*-\s*([\d.]+)\s*$", obx7)
    if m:
        return m.group(1), m.group(2)
    return "", ""


def _msh_message_type(fields: list[str]) -> str:
    if len(fields) < 9:
        return ""
    return fields[8].strip()


def _msh_control_id(fields: list[str]) -> str:
    if len(fields) < 10:
        return ""
    return fields[9].strip()


def build_ack(*, control_id: str, ack_code: str = "AA") -> bytes:
    """ACK^R01 with MSA|AA|control_id (Mindray BC-60R HL7 doc)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    # New outbound control id for ACK message
    out_cid = f"A{ts}"
    lines = [
        f"MSH|^~\\&|lab_connector||||{ts}||ACK^R01|{out_cid}|P|2.3.1||||||UNICODE",
        f"MSA|{ack_code}|{control_id}",
    ]
    text = "\r".join(lines) + "\r"
    return text.encode("utf-8")


def oru_r01_to_veto_json(
    hl7_text: str,
    *,
    sample_scheme: str = "barcode",
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Parse ORU^R01 → Veto ingest JSON dict, or (None, error).
    Returns (None, None) if message is not ORU^R01 (caller may still ACK).
    """
    text = hl7_text.replace("\r\n", "\r").replace("\n", "\r")
    lines = [ln for ln in text.split("\r") if ln.strip()]
    if not lines:
        return None, "empty_message"

    msh = lines[0]
    if not msh.startswith("MSH|"):
        return None, "missing_msh"

    msh_f = _split_fields(msh)
    mt = _msh_message_type(msh_f)
    if mt != "ORU^R01":
        return None, None  # not an error — not our payload type

    obr_lines = [ln for ln in lines if ln.startswith("OBR|")]
    obx_lines = [ln for ln in lines if ln.startswith("OBX|")]
    if not obr_lines:
        return None, "missing_obr"

    obr_f = _split_fields(obr_lines[0])
    # HL7: OBR-3 = Filler Order Number = sample ID for results (BC-60R doc)
    if len(obr_f) < 4:
        return None, "obr_missing_sample_id"
    sample_id = obr_f[3].strip()
    if not sample_id:
        return None, "empty_sample_id"

    observations: list[dict[str, Any]] = []
    for obx in obx_lines:
        f = _split_fields(obx)
        if len(f) < 6:
            continue
        set_id = f[1].strip() if len(f) > 1 else "0"
        obx3 = f[3] if len(f) > 3 else ""
        vendor_code = _first_component(obx3)
        if not vendor_code:
            continue
        name_parts = obx3.split("^")
        vendor_name = name_parts[1] if len(name_parts) > 1 else ""

        value = f[5] if len(f) > 5 else ""
        unit = _first_component(f[6]) if len(f) > 6 else ""
        ref_raw = f[7] if len(f) > 7 else ""
        ref_low, ref_high = _parse_ref_range(ref_raw)
        flag = f[8].strip() if len(f) > 8 else ""

        obs: dict[str, Any] = {
            "vendor_code": vendor_code,
            "natural_key": set_id or str(len(observations)),
            "vendor_name": vendor_name,
            "value_text": value,
            "unit": unit,
            "ref_low": ref_low,
            "ref_high": ref_high,
            "abnormal_flag": flag,
        }
        try:
            float(value.replace(",", "."))
            obs["value_numeric"] = str(value.replace(",", "."))
        except ValueError:
            pass

        observations.append(obs)

    if not observations:
        return None, "no_obx_observations"

    payload: dict[str, Any] = {
        "identifiers": [{"scheme": sample_scheme, "value": sample_id}],
        "observations": observations,
        "metadata": {
            "hl7_message_type": "ORU^R01",
            "connector": "lab_connector_bc60r",
            "version": "0.1",
        },
    }
    return payload, None


def veto_json_dumps(body: dict[str, Any]) -> bytes:
    return json.dumps(body, ensure_ascii=False).encode("utf-8")


def extract_control_id(hl7_text: str) -> str:
    lines = hl7_text.replace("\r\n", "\r").replace("\n", "\r").split("\r")
    if not lines or not lines[0].startswith("MSH|"):
        return "UNKNOWN"
    f = lines[0].split("|")
    return f[9].strip() if len(f) > 9 else "UNKNOWN"
