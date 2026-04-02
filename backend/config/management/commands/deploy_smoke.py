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
            help=(
                "Bearer access token from POST /api/auth/token/ (field access). "
                "If empty or missing login, auth check is skipped. "
                "Do not pass the literal string 'null' from a failed jq."
            ),
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
        if token.lower() in ("null", "none"):
            token = ""
        timeout = max(1, int(options["timeout"]))

        results: list[tuple[str, int, bool]] = []

        for path in ("/health/", "/health/ready/"):
            url = f"{base}{path}"
            code, ok, err = self._get_json(url, timeout=timeout, expect_ok_envelope=True)
            results.append((path, code, ok))
            if not ok:
                raise CommandError(self._format_failure("GET", url, code, err))

        if token:
            url = f"{base}/api/me/"
            code, ok, err = self._get_json(
                url,
                timeout=timeout,
                headers={"Authorization": f"Bearer {token}"},
                expect_ok_envelope=False,
            )
            results.append(("/api/me/", code, ok))
            if not ok:
                raise CommandError(self._format_failure("GET", url, code, err))

        payload = {"ok": True, "checks": [{"path": p, "status": c} for p, c, _ in results]}
        self.stdout.write(json.dumps(payload, ensure_ascii=False))

    @staticmethod
    def _format_failure(method: str, url: str, code: int, err: str | None) -> str:
        parts = [f"check failed: {method} {url}", f"HTTP {code}"]
        if err:
            parts.append(err)
        if code == 0:
            parts.append(
                "(no HTTP response — wrong DEPLOY_SMOKE_BASE_URL, DNS unreachable host, "
                "TLS error, or use http:// for local dev)"
            )
        return " — ".join(parts)

    @staticmethod
    def _get_json(
        url: str,
        *,
        timeout: int,
        headers: dict[str, str] | None = None,
        expect_ok_envelope: bool = True,
    ) -> tuple[int, bool, str | None]:
        req = urllib.request.Request(url, method="GET", headers=dict(headers or {}))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = resp.getcode()
                body = resp.read()
        except urllib.error.HTTPError as e:
            hint: str | None = None
            try:
                raw = e.read().decode("utf-8", errors="replace")
                if raw:
                    hint = raw[:500]
            except Exception:
                pass
            return e.code, False, hint or getattr(e, "reason", None) or str(e)
        except urllib.error.URLError as e:
            reason = e.reason
            msg = str(reason) if reason is not None else str(e)
            return 0, False, msg
        except TimeoutError:
            return 0, False, "request timed out"
        try:
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return code, False, f"response is not JSON: {e}"
        if expect_ok_envelope:
            if data.get("ok") is not True:
                return code, False, f'expected {{"ok": true}}, got {data!r}'
        else:
            # GET /api/me/ returns a user object (no top-level "ok").
            if not isinstance(data, dict) or "id" not in data or "username" not in data:
                return code, False, f"expected user shape with id/username, got {data!r}"
        return code, True, None
