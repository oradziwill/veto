from __future__ import annotations

import socket
from dataclasses import dataclass


@dataclass
class DiscoveredDevice:
    external_ref: str
    device_type: str
    name: str
    vendor: str
    model: str
    serial_number: str
    connection_type: str
    connection_config: dict[str, object]
    capabilities: list[str]
    lifecycle_state: str = "discovered"


def scan_local_devices(listen_host: str, listen_port: int) -> list[DiscoveredDevice]:
    out: list[DiscoveredDevice] = []
    out.append(
        DiscoveredDevice(
            external_ref=f"lab-mllp-{listen_host}:{listen_port}",
            device_type="lab",
            name="Lab MLLP Listener",
            vendor="VETO",
            model="HL7 MLLP Bridge",
            serial_number="",
            connection_type="tcp_server",
            connection_config={"host": listen_host, "port": listen_port},
            capabilities=["hl7_mllp_server", "lab_ingest"],
            lifecycle_state="active",
        )
    )
    out.extend(_scan_serial_candidates())
    out.extend(_scan_local_lan_candidates())
    return out


def _scan_serial_candidates() -> list[DiscoveredDevice]:
    rows: list[DiscoveredDevice] = []
    try:
        from serial.tools import list_ports
    except Exception:
        return rows
    for p in list_ports.comports():
        label = f"{p.device} {p.description}".lower()
        dtype = "fiscal" if any(k in label for k in ("elzab", "fisk", "fiscal")) else "lab"
        rows.append(
            DiscoveredDevice(
                external_ref=f"serial:{p.device}",
                device_type=dtype,
                name=p.description or p.device,
                vendor=_guess_vendor(label),
                model=p.product or "",
                serial_number=p.serial_number or "",
                connection_type="serial",
                connection_config={"port": p.device},
                capabilities=["status_probe"],
                lifecycle_state="discovered",
            )
        )
    return rows


def _scan_local_lan_candidates() -> list[DiscoveredDevice]:
    ports = [2575, 9100]
    rows: list[DiscoveredDevice] = []
    for port in ports:
        if _can_connect("127.0.0.1", port):
            dtype = "lab" if port == 2575 else "fiscal"
            rows.append(
                DiscoveredDevice(
                    external_ref=f"lan:127.0.0.1:{port}",
                    device_type=dtype,
                    name=f"Local TCP endpoint {port}",
                    vendor="Unknown",
                    model="Unknown",
                    serial_number="",
                    connection_type="tcp",
                    connection_config={"host": "127.0.0.1", "port": port},
                    capabilities=["status_probe"],
                    lifecycle_state="confirmed",
                )
            )
    return rows


def _can_connect(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.15):
            return True
    except Exception:
        return False


def _guess_vendor(label: str) -> str:
    if "elzab" in label:
        return "ELZAB"
    if "mindray" in label:
        return "Mindray"
    return "Unknown"
