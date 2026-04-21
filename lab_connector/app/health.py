from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
import json

log = logging.getLogger(__name__)


def start_health_server(
    host: str,
    port: int,
    *,
    is_healthy: Callable[[], bool],
    metrics_payload: Callable[[], dict[str, object]] | None = None,
) -> ThreadingHTTPServer:
    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            log.debug(fmt, *args)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/metrics":
                payload = metrics_payload() if metrics_payload else {}
                body = json.dumps(payload, sort_keys=True).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path != "/health":
                self.send_error(404)
                return
            if is_healthy():
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"ok\n")
            else:
                self.send_response(503)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"degraded\n")

    httpd = ThreadingHTTPServer((host, port), H)
    t = threading.Thread(target=httpd.serve_forever, daemon=True, name="health-http")
    t.start()
    log.info("Health HTTP on http://%s:%s/health", host, port)
    return httpd
