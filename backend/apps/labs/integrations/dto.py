from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class IdentifierDraft:
    scheme: str
    value: str


@dataclass
class ObservationDraft:
    vendor_code: str
    natural_key: str
    vendor_name: str = ""
    value_text: str = ""
    value_numeric: Decimal | None = None
    unit: str = ""
    ref_low: str = ""
    ref_high: str = ""
    abnormal_flag: str = ""
    result_status: str = ""
    observed_at: datetime | None = None


@dataclass
class ParsedIngestPayload:
    identifiers: list[IdentifierDraft]
    observations: list[ObservationDraft]
    metadata: dict[str, Any]
