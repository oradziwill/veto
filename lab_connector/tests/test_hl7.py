from app.hl7 import (
    build_ack,
    extract_control_id,
    extract_mllp_frames,
    oru_r01_to_veto_json,
    wrap_mllp,
)


def test_mllp_roundtrip() -> None:
    raw = b"MSH|^~\\&|x\rPID|1||id\r"
    buf = bytearray(wrap_mllp(raw) + wrap_mllp(raw))
    assert extract_mllp_frames(buf) == [raw, raw]
    assert len(buf) == 0


def test_oru_to_json_minimal() -> None:
    hl7 = (
        "MSH|^~\\&| |Mindray|||20210312092538||ORU^R01|2|P|2.3.1||||||UNICODE\r"
        "PID|1||7393670^^^^MR||Jerry^Tom||20210312092538|Male\r"
        "OBR|1||SAMPLE-001|00001^Automated Count^99MRC||||||||||||||||||||HM||||||||admin\r"
        "OBX|1|NM|6690-2^WBC^LN||9.55|10*9/L|6.00-17.00||||F\r"
    )
    payload, err = oru_r01_to_veto_json(hl7, sample_scheme="barcode")
    assert err is None
    assert payload is not None
    assert payload["identifiers"] == [{"scheme": "barcode", "value": "SAMPLE-001"}]
    assert len(payload["observations"]) == 1
    o0 = payload["observations"][0]
    assert o0["vendor_code"] == "6690-2"
    assert o0["vendor_name"] == "WBC"
    assert o0["value_text"] == "9.55"
    assert o0["ref_low"] == "6.00"
    assert o0["ref_high"] == "17.00"


def test_non_oru_returns_none_tuple() -> None:
    hl7 = "MSH|^~\\&| |Mindray|||20210312092538||ACK^R01|2|P|2.3.1||||||UNICODE\r"
    payload, err = oru_r01_to_veto_json(hl7)
    assert payload is None and err is None


def test_control_id_and_ack() -> None:
    hl7 = "MSH|^~\\&| |Mindray|||20210312092538||ORU^R01|99|P|2.3.1||||||UNICODE\r"
    assert extract_control_id(hl7) == "99"
    ack = build_ack(control_id="99", ack_code="AA")
    assert ack.startswith(b"MSH|")
    assert b"MSA|AA|99" in ack
