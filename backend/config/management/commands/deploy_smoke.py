from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from django.core.management.base import BaseCommand, CommandError

DEFAULT_TIMEOUT_SEC = 15


class Command(BaseCommand):
    help = (
        "Post-deploy smoke: GET /health/, /health/ready/, and optionally GET /api/me/ "
        "with DEPLOY_SMOKE_JWT or --jwt (staff access token)."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--base-url",
            default=os.environ.get("DEPLOY_SMOKE_BASE_URL", "http://127.0.0.1:8000"),
            help="Origin including scheme, no trailing path (default: env DEPLOY_SMOKE_BASE_URL or localhost:8000).",
        )
        parser.add_argument(
            "--jwt",
            default=os.environ.get("DEPLOY_SMOKE_JWT", ""),
            help="Bearer access token for /api/me/ (default: env DEPLOY_SMOKE_JWT). If empty, auth check is skipped.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=int(os.environ.get("DEPLOY_SMOKE_TIMEOUT_SEC", DEFAULT_TIMEOUT_SEC)),
            help="Per-request timeout in seconds.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        base = str(options["base_url"]).rstrip("/")
        token = str(options["jwt"] or "").strip()
        timeout = max(1, int(options["timeout"]))

        results: list[tuple[str, int, bool]] = []

        for path in ("/health/", "/health/ready/"):
            url = f"{base}{path}"
            code, ok = self._get_json(url, timeout=timeout)
            results.append((path, code, ok))
            if not ok:
                raise CommandError(f"check failed: {path} -> HTTP {code}")

        if token:
            url = f"{base}/api/me/"
            code, ok = self._get_json(
                url,
                timeout=timeout,
                headers={"Authorization": f"Bearer {token}"},
            )
            results.append(("/api/me/", code, ok))
            if not ok:
                raise CommandError(f"check failed: /api/me/ -> HTTP {code}")

        payload = {"ok": True, "checks": [{"path": p, "status": c} for p, c, _ in results]}
        self.stdout.write(json.dumps(payload, ensure_ascii=False))

    @staticmethod
    def _get_json(
        url: str,
        *,
        timeout: int,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bool]:
        req = urllib.request.Request(url, method="GET", headers=dict(headers or {}))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = getattr(resp, "status", 200) or 200
                body = resp.read()
        except urllib.error.HTTPError as e:
            return e.code, False
        except urllib.error.URLError:
            return 0, False
        try:
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return code, False
        return code, bool(data.get("ok") is True)
