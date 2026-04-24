from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class PrintResult:
    success: bool
    message: str
    fiscal_number: str = ""


@dataclass
class DeviceStatus:
    online: bool
    status_message: str


class FiscalDriver(Protocol):
    def print_receipt(self, payload: dict[str, object]) -> PrintResult:
        ...

    def get_status(self) -> DeviceStatus:
        ...
