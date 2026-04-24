from __future__ import annotations

import hashlib

from app.fiscal.base import DeviceStatus, PrintResult


class MockFiscalDriver:
    def print_receipt(self, payload: dict[str, object]) -> PrintResult:
        rid = str(payload.get("receipt_id", ""))
        idem = str(payload.get("idempotency_key", ""))
        digest = hashlib.sha1(f"{rid}:{idem}".encode("utf-8")).hexdigest()[:12]
        return PrintResult(success=True, message="Mock print successful", fiscal_number=f"MOCK-{digest}")

    def get_status(self) -> DeviceStatus:
        return DeviceStatus(online=True, status_message="mock_driver_online")
