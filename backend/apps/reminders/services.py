from __future__ import annotations

import base64
import json
import logging
from datetime import UTC, datetime, timedelta
from urllib import error, parse, request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone

from .models import Reminder, ReminderPreference

logger = logging.getLogger(__name__)


def send_reminder(reminder: Reminder) -> tuple[str, str]:
    """
    Provider-agnostic delivery entrypoint. Returns (message_id, provider_status).
    """
    if reminder.channel == Reminder.Channel.EMAIL:
        return _send_email(reminder)
    if reminder.channel == Reminder.Channel.SMS:
        return _send_sms(reminder)
    raise ValueError(f"Unsupported reminder channel: {reminder.channel}")


def _send_email(reminder: Reminder) -> tuple[str, str]:
    if not reminder.recipient:
        raise ValueError("Cannot send email reminder without recipient.")
    provider = str(getattr(settings, "REMINDER_EMAIL_PROVIDER", "internal")).lower()
    reminder.provider = (
        Reminder.Provider.SENDGRID
        if provider == Reminder.Provider.SENDGRID
        else Reminder.Provider.INTERNAL
    )
    if reminder.provider == Reminder.Provider.SENDGRID:
        return _send_via_sendgrid(reminder)
    logger.info(
        "reminder_email_sent reminder_id=%s provider=%s recipient=%s type=%s",
        reminder.id,
        provider,
        reminder.recipient,
        reminder.reminder_type,
    )
    return f"email-{reminder.id}", "accepted"


def _send_sms(reminder: Reminder) -> tuple[str, str]:
    if not reminder.recipient:
        raise ValueError("Cannot send SMS reminder without recipient.")
    provider = str(getattr(settings, "REMINDER_SMS_PROVIDER", "internal")).lower()
    reminder.provider = (
        Reminder.Provider.TWILIO
        if provider == Reminder.Provider.TWILIO
        else Reminder.Provider.INTERNAL
    )
    if reminder.provider == Reminder.Provider.TWILIO:
        return _send_via_twilio(reminder)
    logger.info(
        "reminder_sms_sent reminder_id=%s provider=%s recipient=%s type=%s",
        reminder.id,
        provider,
        reminder.recipient,
        reminder.reminder_type,
    )
    return f"sms-{reminder.id}", "accepted"


def pick_channel_and_recipient(
    preference: ReminderPreference | None, *, email: str, phone: str
) -> tuple[str, str]:
    if preference is None:
        if email:
            return Reminder.Channel.EMAIL, email
        if phone:
            return Reminder.Channel.SMS, phone
        return "", ""

    pref = preference.preferred_channel
    can_email = preference.allow_email and bool(email)
    can_sms = preference.allow_sms and bool(phone)

    if pref == ReminderPreference.PreferredChannel.EMAIL and can_email:
        return Reminder.Channel.EMAIL, email
    if pref == ReminderPreference.PreferredChannel.SMS and can_sms:
        return Reminder.Channel.SMS, phone

    if can_email:
        return Reminder.Channel.EMAIL, email
    if can_sms:
        return Reminder.Channel.SMS, phone
    return "", ""


def should_defer_for_quiet_hours(
    reminder: Reminder, preference: ReminderPreference | None, now=None
) -> tuple[bool, datetime | None]:
    now = now or timezone.now()
    if preference is None:
        return False, None
    if not (preference.quiet_hours_start and preference.quiet_hours_end):
        return False, None

    try:
        zone = ZoneInfo(preference.timezone or "UTC")
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("UTC")

    local_now = now.astimezone(zone)
    current_time = local_now.timetz().replace(tzinfo=None)
    start = preference.quiet_hours_start
    end = preference.quiet_hours_end
    in_quiet = _is_time_in_quiet_window(current_time, start, end)
    if not in_quiet:
        return False, None
    next_allowed = _next_allowed_local_datetime(local_now, start, end)
    return True, next_allowed.astimezone(UTC)


def _is_time_in_quiet_window(current_time, start, end) -> bool:
    if start == end:
        return True
    if start < end:
        return start <= current_time < end
    return current_time >= start or current_time < end


def _next_allowed_local_datetime(local_now, start, end):
    today_end = local_now.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if start < end:
        return today_end if local_now < today_end else today_end + timedelta(days=1)
    # quiet window wraps midnight; if we are after start, wait until tomorrow end
    if local_now.timetz().replace(tzinfo=None) >= start:
        return today_end + timedelta(days=1)
    return today_end


def _send_via_sendgrid(reminder: Reminder) -> tuple[str, str]:
    api_key = str(getattr(settings, "REMINDER_SENDGRID_API_KEY", "")).strip()
    from_email = str(getattr(settings, "REMINDER_SENDGRID_FROM_EMAIL", "")).strip()
    from_name = str(getattr(settings, "REMINDER_SENDGRID_FROM_NAME", "Veto Clinic")).strip()
    if not api_key:
        raise ValueError("SendGrid API key is not configured.")
    if not from_email:
        raise ValueError("SendGrid from email is not configured.")

    payload = {
        "from": {"email": from_email, "name": from_name},
        "personalizations": [{"to": [{"email": reminder.recipient}]}],
        "subject": reminder.subject or "Clinic reminder",
        "content": [{"type": "text/plain", "value": reminder.body or ""}],
        "custom_args": {"reminder_id": str(reminder.id)},
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
    message_id = response.headers.get("X-Message-Id") or f"sendgrid-{reminder.id}"
    return message_id, "accepted"


def _send_via_twilio(reminder: Reminder) -> tuple[str, str]:
    account_sid = str(getattr(settings, "REMINDER_TWILIO_ACCOUNT_SID", "")).strip()
    auth_token = str(getattr(settings, "REMINDER_TWILIO_AUTH_TOKEN", "")).strip()
    from_number = str(getattr(settings, "REMINDER_TWILIO_FROM_NUMBER", "")).strip()
    if not account_sid or not auth_token:
        raise ValueError("Twilio credentials are not configured.")
    if not from_number:
        raise ValueError("Twilio from number is not configured.")

    form_payload = {
        "From": from_number,
        "To": reminder.recipient,
        "Body": reminder.body or reminder.subject or "Clinic reminder",
    }
    status_callback = str(getattr(settings, "REMINDER_TWILIO_STATUS_CALLBACK_URL", "")).strip()
    if status_callback:
        form_payload["StatusCallback"] = status_callback
    body = parse.urlencode(form_payload).encode("utf-8")
    basic = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode("ascii")
    req = request.Request(
        url=f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        response = request.urlopen(req, timeout=15)
        payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise ValueError(f"Twilio request failed: {exc.code} {detail}") from exc
    except error.URLError as exc:
        raise ValueError(f"Twilio connection failed: {exc.reason}") from exc

    sid = payload.get("sid", "")
    status_value = payload.get("status", "accepted")
    if not sid:
        raise ValueError("Twilio response did not include sid.")
    return sid, str(status_value)
