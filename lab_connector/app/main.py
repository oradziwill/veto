from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")

from app.config import Settings  # noqa: E402
from app.health import start_health_server  # noqa: E402
from app.metrics import ConnectorMetrics  # noqa: E402
from app.outbox import Outbox  # noqa: E402
from app.tcp_server import run_tcp_server  # noqa: E402
from app.worker import outbox_loop  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("lab_connector")


async def _run() -> None:
    settings = Settings()
    outbox = Outbox(settings.outbox_db_path, settings.retry_backoff_sec)
    metrics = ConnectorMetrics()
    stop = asyncio.Event()

    start_health_server(
        settings.health_host,
        settings.health_port,
        is_healthy=lambda: True,
        metrics_payload=metrics.snapshot,
    )

    srv = await run_tcp_server(settings, outbox, metrics)
    loop = asyncio.get_running_loop()

    def _shutdown() -> None:
        log.info("Shutdown signal")
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _shutdown)

    async with srv:
        worker = asyncio.create_task(outbox_loop(settings, outbox, stop, metrics), name="outbox")
        try:
            await stop.wait()
        finally:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
