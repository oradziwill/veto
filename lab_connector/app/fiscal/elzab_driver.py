from __future__ import annotations

from app.fiscal.base import DeviceStatus, PrintResult


class ElzabFiscalDriver:
    """
    Placeholder for ELZAB protocol implementation.

    TODO:
    - Confirm transport by model (USB/RS232/LAN).
    - Implement session open/close lifecycle.
    - Map payload items/payments to official ELZAB command set.
    - Handle legal/compliance edge cases (NIP timing, duplicate prevention, print errors).
    """

    def print_receipt(self, payload: dict[str, object]) -> PrintResult:
        return PrintResult(
            success=False,
            message="ELZAB driver not implemented yet. Use MockFiscalDriver until vendor protocol is confirmed.",
        )

    def get_status(self) -> DeviceStatus:
        return DeviceStatus(online=False, status_message="elzab_driver_not_implemented")
