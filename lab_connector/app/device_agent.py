from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.agent_store import AgentStore
from app.device_api import (
    post_command_result,
    post_heartbeat,
    pull_commands,
    register_agent,
    upsert_inventory,
)
from app.device_scan import scan_local_devices
from app.fiscal.elzab_driver import ElzabFiscalDriver
from app.fiscal.mock_driver import MockFiscalDriver

if TYPE_CHECKING:
    from app.config import Settings
    from app.metrics import ConnectorMetrics

log = logging.getLogger(__name__)


async def run_device_agent(settings: Settings, stop: asyncio.Event, metrics: ConnectorMetrics) -> None:
    if not settings.dm_base_url:
        log.warning("Device agent enabled but DM_BASE_URL missing; skipping.")
        return
    ok, msg = await asyncio.to_thread(register_agent, settings)
    if ok:
        log.info("Device agent registered: %s", msg)
    else:
        log.warning("Device agent register failed: %s", msg)
    store = AgentStore(Path(settings.outbox_db_path).with_name("agent_store.sqlite3"))
    inventory_task = asyncio.create_task(_inventory_loop(settings, stop, metrics), name="dm-inventory")
    command_task = asyncio.create_task(_command_loop(settings, stop, store, metrics), name="dm-commands")
    try:
        await stop.wait()
    finally:
        for task in (inventory_task, command_task):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


async def _inventory_loop(settings: Settings, stop: asyncio.Event, metrics: ConnectorMetrics) -> None:
    while not stop.is_set():
        devices = await asyncio.to_thread(scan_local_devices, settings.listen_host, settings.listen_port)
        ok, msg = await asyncio.to_thread(upsert_inventory, settings, devices)
        if ok:
            metrics.inc("dm_inventory_success_total")
        else:
            metrics.inc("dm_inventory_fail_total")
            log.warning("Inventory upsert failed: %s", msg)
        hb_ok, hb_msg = await asyncio.to_thread(
            post_heartbeat,
            settings,
            {"discovered_devices": len(devices), "inventory_status": msg},
        )
        if hb_ok:
            metrics.inc("dm_heartbeat_success_total")
        else:
            metrics.inc("dm_heartbeat_fail_total")
            log.warning("Heartbeat failed: %s", hb_msg)
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.dm_inventory_poll_sec)
        except TimeoutError:
            pass


async def _command_loop(
    settings: Settings,
    stop: asyncio.Event,
    store: AgentStore,
    metrics: ConnectorMetrics,
) -> None:
    mock_driver = MockFiscalDriver()
    elzab_driver = ElzabFiscalDriver()
    while not stop.is_set():
        ok, payload = await asyncio.to_thread(pull_commands, settings)
        if not ok:
            metrics.inc("dm_command_pull_fail_total")
            log.warning("Command pull failed: %s", payload)
            await asyncio.sleep(settings.dm_command_poll_sec)
            continue
        metrics.inc("dm_command_pull_success_total")
        commands = payload if isinstance(payload, list) else []
        for cmd in commands:
            await _process_command(settings, cmd, store, metrics, mock_driver, elzab_driver)
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.dm_command_poll_sec)
        except TimeoutError:
            pass


async def _process_command(
    settings: Settings,
    cmd: dict[str, object],
    store: AgentStore,
    metrics: ConnectorMetrics,
    mock_driver: MockFiscalDriver,
    elzab_driver: ElzabFiscalDriver,
) -> None:
    command_id = int(cmd.get("id") or 0)
    command_type = str(cmd.get("command_type") or "")
    if command_id <= 0:
        return
    already = await asyncio.to_thread(store.get_processed, command_id)
    if already:
        metrics.inc("dm_command_duplicate_blocked_total")
        await asyncio.to_thread(
            post_command_result,
            settings,
            command_id,
            str(already["status"]),
            {"fiscal_number": str(already["fiscal_number"])},
            "",
        )
        return
    if command_type != "fiscal_print":
        await asyncio.to_thread(
            post_command_result,
            settings,
            command_id,
            "failed",
            {},
            f"Unsupported command_type={command_type}",
        )
        await asyncio.to_thread(store.upsert_processed, command_id, "failed", "")
        metrics.inc("dm_command_unsupported_total")
        return
    payload = cmd.get("payload") if isinstance(cmd.get("payload"), dict) else {}
    use_elzab = str(payload.get("driver") or "").lower() == "elzab"
    driver = elzab_driver if use_elzab else mock_driver
    result = await asyncio.to_thread(driver.print_receipt, payload)
    status = "succeeded" if result.success else "failed"
    err = "" if result.success else result.message
    await asyncio.to_thread(
        post_command_result,
        settings,
        command_id,
        status,
        {"message": result.message, "fiscal_number": result.fiscal_number},
        err,
    )
    await asyncio.to_thread(store.upsert_processed, command_id, status, result.fiscal_number)
    if result.success:
        metrics.inc("dm_command_fiscal_success_total")
    else:
        metrics.inc("dm_command_fiscal_fail_total")
