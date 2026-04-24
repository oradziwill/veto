from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from app.config import Settings
    from app.device_scan import DiscoveredDevice

log = logging.getLogger(__name__)


def _headers(settings: Settings) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if settings.dm_bearer_token:
        h["Authorization"] = f"Bearer {settings.dm_bearer_token}"
    return h


def register_agent(settings: Settings) -> tuple[bool, str]:
    if not settings.dm_base_url:
        return False, "DM_BASE_URL is empty"
    payload = {
        "clinic_id": settings.dm_clinic_id,
        "node_id": settings.dm_node_id,
        "name": settings.dm_node_name,
        "version": "0.1.0",
        "host": settings.listen_host,
        "metadata": {"component": "lab_connector"},
    }
    try:
        r = httpx.post(
            f"{settings.dm_base_url}/api/device-management/agents/register/",
            json=payload,
            headers=_headers(settings),
            timeout=10.0,
        )
        if 200 <= r.status_code < 300:
            return True, f"register status={r.status_code}"
        return False, f"register status={r.status_code} body={r.text[:200]}"
    except Exception as e:
        return False, str(e)


def post_heartbeat(settings: Settings, payload: dict[str, object]) -> tuple[bool, str]:
    body = {
        "clinic_id": settings.dm_clinic_id,
        "node_id": settings.dm_node_id,
        "status": "online",
        "host": settings.listen_host,
        "payload": payload,
    }
    try:
        r = httpx.post(
            f"{settings.dm_base_url}/api/device-management/agents/heartbeat/",
            json=body,
            headers=_headers(settings),
            timeout=10.0,
        )
        if 200 <= r.status_code < 300:
            return True, f"heartbeat status={r.status_code}"
        return False, f"heartbeat status={r.status_code} body={r.text[:200]}"
    except Exception as e:
        return False, str(e)


def upsert_inventory(settings: Settings, devices: list[DiscoveredDevice]) -> tuple[bool, str]:
    body = {
        "clinic_id": settings.dm_clinic_id,
        "node_id": settings.dm_node_id,
        "devices": [
            {
                "external_ref": d.external_ref,
                "device_type": d.device_type,
                "lifecycle_state": d.lifecycle_state,
                "name": d.name,
                "vendor": d.vendor,
                "model": d.model,
                "serial_number": d.serial_number,
                "connection_type": d.connection_type,
                "connection_config": d.connection_config,
                "capabilities": d.capabilities,
                "is_active": True,
            }
            for d in devices
        ],
    }
    try:
        r = httpx.post(
            f"{settings.dm_base_url}/api/device-management/devices/upsert/",
            json=body,
            headers=_headers(settings),
            timeout=15.0,
        )
        if 200 <= r.status_code < 300:
            return True, f"inventory status={r.status_code}"
        return False, f"inventory status={r.status_code} body={r.text[:200]}"
    except Exception as e:
        return False, str(e)


def pull_commands(settings: Settings) -> tuple[bool, list[dict[str, object]] | str]:
    try:
        r = httpx.get(
            f"{settings.dm_base_url}/api/device-management/agent/commands/",
            params={"node_id": settings.dm_node_id, "clinic_id": settings.dm_clinic_id},
            headers=_headers(settings),
            timeout=10.0,
        )
        if 200 <= r.status_code < 300:
            return True, list(r.json())
        return False, f"pull status={r.status_code} body={r.text[:200]}"
    except Exception as e:
        return False, str(e)


def post_command_result(
    settings: Settings, command_id: int, status: str, result_payload: dict[str, object], error_message: str = ""
) -> tuple[bool, str]:
    body = {
        "status": status,
        "result_payload": result_payload,
        "error_message": error_message,
    }
    try:
        r = httpx.post(
            f"{settings.dm_base_url}/api/device-management/agent/commands/{command_id}/result/",
            json=body,
            headers=_headers(settings),
            timeout=10.0,
        )
        if 200 <= r.status_code < 300:
            return True, f"result status={r.status_code}"
        return False, f"result status={r.status_code} body={r.text[:200]}"
    except Exception as e:
        return False, str(e)
