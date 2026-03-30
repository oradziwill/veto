"""
Send portal login OTP via SendGrid (same API credentials as reminder email delivery).
"""

from __future__ import annotations

import json
import logging
from urllib import error, request

from django.conf import settings

logger = logging.getLogger(__name__)


def sendgrid_configured() -> bool:
    return bool(
        str(getattr(settings, "REMINDER_SENDGRID_API_KEY", "")).strip()
        and str(getattr(settings, "REMINDER_SENDGRID_FROM_EMAIL", "")).strip()
    )


def send_portal_otp_email(
    *,
    to_email: str,
    code: str,
    clinic_name: str,
    magic_link_url: str | None = None,
    magic_plain_token: str | None = None,
) -> None:
    """
    Raises ValueError if SendGrid returns an error response.
    When magic_link_url is set, adds a one-click sign-in line; otherwise may append
    magic_plain_token for copy-paste in the app if provided.
    """
    api_key = str(getattr(settings, "REMINDER_SENDGRID_API_KEY", "")).strip()
    from_email = str(getattr(settings, "REMINDER_SENDGRID_FROM_EMAIL", "")).strip()
    from_name = str(getattr(settings, "REMINDER_SENDGRID_FROM_NAME", "Veto Clinic")).strip()
    if not api_key or not from_email:
        raise ValueError("SendGrid is not configured (REMINDER_SENDGRID_API_KEY / FROM_EMAIL).")

    expire = int(getattr(settings, "PORTAL_OTP_EXPIRE_MINUTES", 15))
    subject = f"Your login code — {clinic_name}"
    body = (
        f"Your login code for {clinic_name} is: {code}\n\n"
        f"This code expires in {expire} minutes.\n"
    )
    if magic_link_url:
        body += f"\nOr sign in with this link:\n{magic_link_url}\n"
    elif magic_plain_token:
        body += (
            "\nOr use this one-time sign-in token in the app (with “magic link” login):\n"
            f"{magic_plain_token}\n"
        )
    body += "\nIf you did not request this, you can ignore this email.\n"
    payload = {
        "from": {"email": from_email, "name": from_name},
        "personalizations": [{"to": [{"email": to_email}]}],
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }
    req = request.Request(
        url="https://api.sendgrid.com/v3/mail/send",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        response = request.urlopen(req, timeout=15)
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise ValueError(f"SendGrid request failed: {exc.code} {detail}") from exc
    except error.URLError as exc:
        raise ValueError(f"SendGrid connection failed: {exc.reason}") from exc

    status_code = getattr(response, "status", 0) or response.getcode()
    if not 200 <= int(status_code) < 300:
        raise ValueError(f"SendGrid request failed with status {status_code}")
    logger.info(
        "portal_otp_email_sent to=%s clinic=%s",
        to_email,
        clinic_name,
    )
