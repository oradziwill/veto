from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.hl7 import (
    build_ack,
    extract_control_id,
    extract_mllp_frames,
    oru_r01_to_veto_json,
    veto_json_dumps,
    wrap_mllp,
)

if TYPE_CHECKING:
    from app.config import Settings
    from app.metrics import ConnectorMetrics
    from app.outbox import Outbox

log = logging.getLogger(__name__)


async def _handle_mllp_payload(
    writer: asyncio.StreamWriter,
    payload: bytes,
    settings: Settings,
    outbox: Outbox,
    metrics: ConnectorMetrics,
) -> None:
    metrics.inc("mllp_frames_received_total")
    text = payload.decode("utf-8", errors="replace")
    cid = extract_control_id(text)

    try:
        parsed, err = oru_r01_to_veto_json(text, sample_scheme=settings.sample_identifier_scheme)
    except Exception as e:
        log.exception("HL7 parse crash: %s", e)
        metrics.inc("hl7_parse_error_total")
        metrics.inc("ack_ae_total")
        writer.write(wrap_mllp(build_ack(control_id=cid, ack_code="AE")))
        await writer.drain()
        return

    if parsed is None and err is None:
        # Not ORU^R01 — acknowledge so client is not blocked
        metrics.inc("hl7_non_oru_total")
        metrics.inc("ack_aa_total")
        writer.write(wrap_mllp(build_ack(control_id=cid, ack_code="AA")))
        await writer.drain()
        return

    if parsed is None:
        log.warning("HL7 reject cid=%s err=%s", cid, err)
        metrics.inc("hl7_reject_total")
        metrics.inc("ack_ae_total")
        writer.write(wrap_mllp(build_ack(control_id=cid, ack_code="AE")))
        await writer.drain()
        return

    body = veto_json_dumps(parsed)
    await asyncio.to_thread(outbox.enqueue, body)
    metrics.inc("outbox_enqueued_total")
    metrics.inc("ack_aa_total")
    writer.write(wrap_mllp(build_ack(control_id=cid, ack_code="AA")))
    await writer.drain()
    log.info("Enqueued ORU^R01 cid=%s bytes=%s", cid, len(body))


async def client_handler(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    *,
    settings: Settings,
    outbox: Outbox,
    metrics: ConnectorMetrics,
) -> None:
    addr = writer.get_extra_info("peername")
    buf = bytearray()
    try:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            buf.extend(chunk)
            frames = extract_mllp_frames(buf)
            for payload in frames:
                await _handle_mllp_payload(writer, payload, settings, outbox, metrics)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Client handler error peer=%s", addr)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def run_tcp_server(settings: Settings, outbox: Outbox, metrics: ConnectorMetrics) -> asyncio.Server:
    srv = await asyncio.start_server(
        lambda r, w: client_handler(r, w, settings=settings, outbox=outbox, metrics=metrics),
        host=settings.listen_host,
        port=settings.listen_port,
    )
    log.info("MLLP TCP listening on %s:%s", settings.listen_host, settings.listen_port)
    return srv
