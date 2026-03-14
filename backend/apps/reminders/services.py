from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
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
