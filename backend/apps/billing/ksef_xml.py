"""
KSeF FA(3) XML invoice builder.

Reference schema: http://crd.gov.pl/wzor/2023/06/29/12648/
"""

from __future__ import annotations

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from xml.dom.minidom import parseString
from xml.etree.ElementTree import Element, SubElement, tostring

FA3_NS = "http://crd.gov.pl/wzor/2023/06/29/12648/"
SYSTEM_INFO = "VetoClinic"


def _sub(parent: Element, tag: str, text: str | None = None, **attrib) -> Element:
    el = SubElement(parent, tag, attrib)
    if text is not None:
        el.text = text
    return el


def _fmt(value: Decimal, places: int = 2) -> str:
    quantizer = Decimal(10) ** -places
    return str(value.quantize(quantizer, rounding=ROUND_HALF_UP))


def _vat_numeric(vat_rate: str) -> Decimal | None:
    """Return numeric VAT rate or None for non-numeric rates (zw, oo, np)."""
    try:
        return Decimal(vat_rate)
    except Exception:
        return None


def build_fa3_xml(invoice) -> bytes:
    """
    Build a KSeF FA(3) XML invoice from a billing.Invoice instance.
    Returns UTF-8 encoded XML bytes.
    """
    clinic = invoice.clinic
    client = invoice.client

    root = Element("Faktura", {"xmlns": FA3_NS})

    # ── Naglowek ──────────────────────────────────────────────────────────────
    header = _sub(root, "Naglowek")
    _sub(header, "KodFormularza", "FA", kodSystemowy="FA (3)", wersjaSchemy="1-0E")
    _sub(header, "WariantFormularza", "3")
    from django.utils.timezone import now as tz_now

    _sub(header, "DataWytworzeniaFa", tz_now().strftime("%Y-%m-%dT%H:%M:%S.000+01:00"))
    _sub(header, "SystemInfo", SYSTEM_INFO)

    # ── Podmiot1 (Seller = Clinic) ─────────────────────────────────────────────
    seller = _sub(root, "Podmiot1")
    dane1 = _sub(seller, "DaneIdentyfikacyjne")
    _sub(dane1, "NIP", clinic.nip or "0000000000")
    _sub(dane1, "Nazwa", clinic.name)
    adres1 = _sub(seller, "Adres")
    _sub(adres1, "KodKraju", "PL")
    _sub(adres1, "AdresL1", clinic.address or clinic.name)
    if clinic.email:
        contact = _sub(seller, "KontaktDanych")
        _sub(contact, "Email", clinic.email)
    if clinic.phone:
        if not clinic.email:
            contact = _sub(seller, "KontaktDanych")
        _sub(contact, "Telefon", clinic.phone)

    # ── Podmiot2 (Buyer = Client) ──────────────────────────────────────────────
    buyer = _sub(root, "Podmiot2")
    dane2 = _sub(buyer, "DaneIdentyfikacyjne")
    full_name = f"{client.first_name} {client.last_name}".strip()
    if client.nip:
        _sub(dane2, "NIP", client.nip)
    else:
        # B2C — no NIP; BrakIDNab=2 means natural person
        _sub(dane2, "BrakIDNab", "2")
    _sub(dane2, "Nazwa", full_name)
    adres2 = _sub(buyer, "Adres")
    _sub(adres2, "KodKraju", "PL")
    addr_line = client.full_address or full_name
    _sub(adres2, "AdresL1", addr_line[:200])

    # ── Fa (Invoice body) ──────────────────────────────────────────────────────
    fa = _sub(root, "Fa")
    _sub(fa, "KodWaluty", invoice.currency or "PLN")

    issue_date = (
        invoice.created_at.date() if invoice.created_at else __import__("datetime").date.today()
    )
    _sub(fa, "P_1", str(issue_date))
    _sub(fa, "P_1M", "Polska")

    inv_number = (
        invoice.invoice_number or f"FV/{issue_date.year}/{issue_date.month:02d}/{invoice.id:04d}"
    )
    _sub(fa, "P_2", inv_number)

    # Service period — use issue date if no specific range
    okres = _sub(fa, "OkresFa")
    _sub(okres, "P_6_Od", str(issue_date))
    _sub(okres, "P_6_Do", str(invoice.due_date or issue_date))

    _sub(fa, "RodzajFaktury", "VAT")

    # ── Line items ─────────────────────────────────────────────────────────────
    net_by_rate: dict[str, Decimal] = defaultdict(Decimal)
    vat_by_rate: dict[str, Decimal] = defaultdict(Decimal)

    lines = list(invoice.lines.all())
    for idx, line in enumerate(lines, start=1):
        row = _sub(fa, "FaWiersz")
        _sub(row, "NrWierszaFa", str(idx))
        _sub(row, "P_7", line.description)
        _sub(row, "P_8A", line.unit or "usł")
        _sub(row, "P_8B", _fmt(line.quantity, 3).rstrip("0").rstrip("."))
        net = line.line_total
        _sub(row, "P_9A", _fmt(line.unit_price))
        _sub(row, "P_11", _fmt(net))
        _sub(row, "P_12", line.vat_rate)

        net_by_rate[line.vat_rate] += net
        numeric = _vat_numeric(line.vat_rate)
        vat_by_rate[line.vat_rate] += (
            (net * numeric / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if numeric
            else Decimal("0")
        )

    # ── Tax totals ─────────────────────────────────────────────────────────────
    # FA3 uses P_13_1 / P_14_1 for 23%, P_13_2 / P_14_2 for 8%, P_13_3 for 5%, etc.
    rate_field_map = {"23": ("1", False), "8": ("2", False), "5": ("3", False), "0": ("4", False)}
    for rate, (suffix, _) in rate_field_map.items():
        if rate in net_by_rate:
            _sub(fa, f"P_13_{suffix}", _fmt(net_by_rate[rate]))
            _sub(fa, f"P_14_{suffix}", _fmt(vat_by_rate[rate]))

    # Exempt (zw) → P_13_6
    if "zw" in net_by_rate:
        _sub(fa, "P_13_6", _fmt(net_by_rate["zw"]))

    # Gross total
    gross = sum(net_by_rate.values(), Decimal("0")) + sum(vat_by_rate.values(), Decimal("0"))
    _sub(fa, "P_15", _fmt(gross))

    # ── Adnotacje (mandatory annotation block) ─────────────────────────────────
    ann = _sub(fa, "Adnotacje")
    _sub(ann, "P_16", "2")  # no self-billing
    _sub(ann, "P_17", "2")  # no cash accounting
    _sub(ann, "P_18", "2")  # not self-issued
    _sub(ann, "P_18A", "2")  # structured invoice (sent via KSeF)
    zwolnienie = _sub(ann, "Zwolnienie")
    _sub(zwolnienie, "P_19N", "1")  # no VAT exemption article
    nst = _sub(ann, "NoweSrodkiTransportu")
    _sub(nst, "P_22N", "1")  # not new transport
    _sub(ann, "P_23", "2")  # not simplified
    pmarzy = _sub(ann, "PMarzy")
    _sub(pmarzy, "P_PMarzy_2N", "1")  # no margin

    # ── Pretty-print ───────────────────────────────────────────────────────────
    raw = tostring(root, encoding="unicode", xml_declaration=False)
    pretty = parseString(f'<?xml version="1.0" encoding="UTF-8"?>{raw}').toprettyxml(
        indent="  ", encoding="UTF-8"
    )
    return pretty
