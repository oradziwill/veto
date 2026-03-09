"""
KSeF API integration service.

Uses the `ksef2` library (https://github.com/artpods56/ksef2).
Install: pip install ksef2   (requires Python 3.12+)

Authentication modes:
  - TEST env:  auto-generated self-signed certificate (no real credentials needed)
  - PROD env:  XAdES certificate from MCU (paths in settings KSEF_CERT_PATH / KSEF_CERT_KEY_PATH)

Django settings:
  KSEF_ENVIRONMENT = "test" | "demo" | "prod"   (default: "test")
  KSEF_CERT_PATH   = "/path/to/cert.pem"         (production only)
  KSEF_CERT_KEY_PATH = "/path/to/key.pem"        (production only)
"""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# ── Environment helper ─────────────────────────────────────────────────────────

def _get_environment():
    try:
        from ksef2 import Environment
    except ImportError as exc:
        raise KSeFError("ksef2 is not installed. Run: pip install ksef2") from exc

    name = getattr(settings, "KSEF_ENVIRONMENT", "test").lower()
    return {
        "test": Environment.TEST,
        "demo": Environment.DEMO,
        "prod": Environment.PRODUCTION,
        "production": Environment.PRODUCTION,
    }.get(name, Environment.TEST)


# ── Public exception ───────────────────────────────────────────────────────────

class KSeFError(Exception):
    pass


# ── Main submission function ───────────────────────────────────────────────────

def submit_invoice(invoice, xml_bytes: bytes) -> str:
    """
    Submit a KSeF XML invoice to the national e-invoicing system.

    Returns the KSeF reference number (str) on success.
    Raises KSeFError on any failure.
    """
    try:
        from ksef2 import Client, Environment
        from ksef2.domain.models import FormSchema
    except ImportError as exc:
        raise KSeFError(
            "ksef2 is not installed. Run: pip install ksef2  (Python 3.12+ required)"
        ) from exc

    clinic = invoice.clinic
    nip = getattr(clinic, "nip", "") or ""
    if not nip:
        raise KSeFError(
            "Clinic NIP is not configured. Please set it in the admin panel."
        )

    env = _get_environment()
    client = Client(env)

    try:
        if env == Environment.TEST:
            auth = client.authentication.with_test_certificate(nip=nip)
        else:
            cert_path = getattr(settings, "KSEF_CERT_PATH", "")
            key_path = getattr(settings, "KSEF_CERT_KEY_PATH", "")
            if not cert_path or not key_path:
                raise KSeFError(
                    "KSEF_CERT_PATH and KSEF_CERT_KEY_PATH must be set in Django settings for non-test environments."
                )
            from pathlib import Path
            from ksef2.core.xades import load_certificate_from_pem, load_private_key_from_pem

            cert = load_certificate_from_pem(Path(cert_path).read_bytes())
            key = load_private_key_from_pem(Path(key_path).read_bytes())
            auth = client.authentication.with_xades(nip=nip, cert=cert, private_key=key)

        with auth.online_session(form_code=FormSchema.FA3) as session:
            result = session.send_invoice(invoice_xml=xml_bytes)
            reference = result.reference_number
            logger.info("Invoice #%s submitted to KSeF. Reference: %s", invoice.id, reference)
            return reference

    except KSeFError:
        raise
    except Exception as exc:
        logger.exception("KSeF submission failed for invoice #%s", invoice.id)
        raise KSeFError(f"KSeF submission failed: {exc}") from exc
