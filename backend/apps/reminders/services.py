from __future__ import annotations

import logging

from .models import Reminder

logger = logging.getLogger(__name__)


def send_reminder(reminder: Reminder) -> str:
    """
    Provider-agnostic delivery entrypoint.
    Returns a synthetic provider message id for observability.
    """
    if reminder.channel == Reminder.Channel.EMAIL:
        return _send_email(reminder)
    if reminder.channel == Reminder.Channel.SMS:
        return _send_sms(reminder)
    raise ValueError(f"Unsupported reminder channel: {reminder.channel}")


def _send_email(reminder: Reminder) -> str:
    if not reminder.recipient:
        raise ValueError("Cannot send email reminder without recipient.")
    logger.info(
        "reminder_email_sent reminder_id=%s recipient=%s type=%s",
        reminder.id,
        reminder.recipient,
        reminder.reminder_type,
    )
    return f"email-{reminder.id}"


def _send_sms(reminder: Reminder) -> str:
    if not reminder.recipient:
        raise ValueError("Cannot send SMS reminder without recipient.")
    logger.info(
        "reminder_sms_sent reminder_id=%s recipient=%s type=%s",
        reminder.id,
        reminder.recipient,
        reminder.reminder_type,
    )
    return f"sms-{reminder.id}"
