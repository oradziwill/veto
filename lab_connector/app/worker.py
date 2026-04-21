from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.veto import deliver_ingest

if TYPE_CHECKING:
    from app.config import Settings
    from app.metrics import ConnectorMetrics
    from app.outbox import Outbox

log = logging.getLogger(__name__)


async def outbox_loop(settings: Settings, outbox: Outbox, stop: asyncio.Event, metrics: ConnectorMetrics) -> None:
    max_att = settings.max_delivery_attempts
    while not stop.is_set():
        rows = await asyncio.to_thread(outbox.fetch_pending, 20)
        for row in rows:
            rid = int(row["id"])
            body = row["body"].encode("utf-8")
            attempts = int(row["attempts"])
            ok, msg = await asyncio.to_thread(deliver_ingest, settings, body)
            if ok:
                await asyncio.to_thread(outbox.mark_delivered, rid)
                metrics.inc("outbox_delivered_total")
                log.info("Delivered outbox id=%s %s", rid, msg)
            else:
                metrics.inc("outbox_delivery_fail_total")
                log.warning("Delivery failed id=%s attempt=%s %s", rid, attempts, msg)
                if attempts + 1 >= max_att:
                    await asyncio.to_thread(outbox.mark_dead, rid, msg)
                    metrics.inc("outbox_dead_total")
                else:
                    await asyncio.to_thread(outbox.mark_retry, rid, attempts, msg)
                    metrics.inc("outbox_retry_scheduled_total")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.outbox_poll_sec)
        except TimeoutError:
            pass
