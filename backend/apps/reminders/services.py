from __future__ import annotations

import base64
import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from urllib import error, parse, request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core import signing
from django.utils import timezone

from .models import (
    Reminder,
    ReminderPortalActionToken,
    ReminderPreference,
    ReminderProviderConfig,
    ReminderTemplate,
)

logger = logging.getLogger(__name__)
PORTAL_SIGNING_SALT = "reminders.portal_action.v1"


class _SafeTemplateDict(dict):
    def __missing__(self, key):
        return ""


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
    provider = resolve_email_provider(clinic_id=reminder.clinic_id)
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
    provider = resolve_sms_provider(clinic_id=reminder.clinic_id)
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


def render_message_template(template: str, context: dict[str, object]) -> str:
    return (template or "").format_map(_SafeTemplateDict(context or {})).strip()


def get_fallback_templates(reminder_type: str) -> tuple[str, str]:
    if reminder_type == Reminder.ReminderType.APPOINTMENT:
        return (
            "Upcoming appointment for {patient_name}",
            "Appointment starts at {appointment_start}.",
        )
    if reminder_type == Reminder.ReminderType.VACCINATION:
        return (
            "Vaccination due soon for {patient_name}",
            "Next dose due at {due_date} for {vaccine_name}.",
        )
    if reminder_type == Reminder.ReminderType.INVOICE:
        return (
            "Invoice reminder for {patient_name}",
            "Invoice #{invoice_number} is due on {due_date}.",
        )
    return ("Clinic reminder", "You have an upcoming clinic reminder.")


def build_reminder_context(
    *,
    clinic_name: str = "",
    patient_name: str = "",
    owner_name: str = "",
    due_date: str = "",
    appointment_start: str = "",
    vaccine_name: str = "",
    invoice_number: str = "",
    confirm_url: str = "",
    cancel_url: str = "",
    reschedule_url: str = "",
) -> dict[str, str]:
    return {
        "clinic_name": clinic_name,
        "patient_name": patient_name,
        "owner_name": owner_name,
        "due_date": due_date,
        "appointment_start": appointment_start,
        "vaccine_name": vaccine_name,
        "invoice_number": invoice_number,
        "confirm_url": confirm_url,
        "cancel_url": cancel_url,
        "reschedule_url": reschedule_url,
    }


def render_reminder_content(
    *,
    clinic_id: int,
    reminder_type: str,
    channel: str,
    locale: str,
    context: dict[str, object],
) -> tuple[str, str]:
    template = (
        ReminderTemplate.objects.filter(
            clinic_id=clinic_id,
            reminder_type=reminder_type,
            channel=channel,
            locale=(locale or ReminderTemplate.Locale.EN),
            is_active=True,
        )
        .only("subject_template", "body_template")
        .first()
    )
    if template:
        subject = render_message_template(template.subject_template, context)
        body = render_message_template(template.body_template, context)
        return subject, body

    fallback_subject, fallback_body = get_fallback_templates(reminder_type)
    return (
        render_message_template(fallback_subject, context),
        render_message_template(fallback_body, context),
    )


def resolve_experiment_variant(
    *,
    reminder_type: str,
    source_object_id: int | None,
    patient_id: int | None,
) -> tuple[str, str]:
    """
    Returns (experiment_key, variant_label).
    For now we run a deterministic A/B split for appointment reminders.
    """
    if reminder_type != Reminder.ReminderType.APPOINTMENT:
        return "", "control"
    token = f"{patient_id or 0}:{source_object_id or 0}".encode()
    bucket = int(hashlib.sha256(token).hexdigest(), 16) % 2
    return "appointment_copy_v1", ("A" if bucket == 0 else "B")


def parse_reply_intent(text: str) -> str:
    normalized = " ".join((text or "").strip().lower().split())
    if not normalized:
        return "unknown"
    if normalized in {"yes", "y", "ok", "confirm", "potwierdzam", "tak"}:
        return "confirm"
    if normalized in {"no", "n", "cancel", "cancelled", "odwolaj", "odwołaj", "nie"}:
        return "cancel"
    if normalized in {
        "reschedule",
        "change",
        "change time",
        "przeloz",
        "przełóż",
        "zmien termin",
        "zmień termin",
    }:
        return "reschedule"
    return "unknown"


def generate_portal_action_token(reminder: Reminder, action: str) -> str:
    ttl_hours = int(str(getattr(settings, "REMINDER_PORTAL_TOKEN_TTL_HOURS", "72")).strip() or "72")
    expires_at = timezone.now() + timedelta(hours=max(1, ttl_hours))
    token_row = ReminderPortalActionToken.objects.create(
        clinic_id=reminder.clinic_id,
        reminder_id=reminder.id,
        action=action,
        expires_at=expires_at,
    )
    payload = {
        "tid": str(token_row.token_id),
        "rid": reminder.id,
        "act": action,
    }
    return signing.dumps(payload, salt=PORTAL_SIGNING_SALT)


def decode_portal_action_token(token: str) -> dict[str, str] | None:
    ttl_hours = int(str(getattr(settings, "REMINDER_PORTAL_TOKEN_TTL_HOURS", "72")).strip() or "72")
    try:
        payload = signing.loads(token, salt=PORTAL_SIGNING_SALT, max_age=max(1, ttl_hours) * 3600)
    except signing.BadSignature:
        return None
    if not isinstance(payload, dict):
        return None
    return {
        "tid": str(payload.get("tid", "")),
        "rid": str(payload.get("rid", "")),
        "act": str(payload.get("act", "")),
    }


def build_portal_action_urls(reminder: Reminder) -> dict[str, str]:
    base_url = str(getattr(settings, "REMINDER_PORTAL_BASE_URL", "")).strip().rstrip("/")
    if not base_url or reminder.reminder_type != Reminder.ReminderType.APPOINTMENT:
        return {"confirm_url": "", "cancel_url": "", "reschedule_url": ""}

    confirm_token = generate_portal_action_token(reminder, ReminderPortalActionToken.Action.CONFIRM)
    cancel_token = generate_portal_action_token(reminder, ReminderPortalActionToken.Action.CANCEL)
    reschedule_token = generate_portal_action_token(
        reminder, ReminderPortalActionToken.Action.RESCHEDULE_REQUEST
    )
    return {
        "confirm_url": f"{base_url}/api/reminders/portal/{confirm_token}/",
        "cancel_url": f"{base_url}/api/reminders/portal/{cancel_token}/",
        "reschedule_url": f"{base_url}/api/reminders/portal/{reschedule_token}/",
    }


def resolve_email_provider(*, clinic_id: int | None) -> str:
    if clinic_id:
        config = (
            ReminderProviderConfig.objects.filter(clinic_id=clinic_id)
            .only("email_provider")
            .first()
        )
        if config:
            return str(config.email_provider).lower()
    return str(getattr(settings, "REMINDER_EMAIL_PROVIDER", "internal")).lower()


def resolve_sms_provider(*, clinic_id: int | None) -> str:
    if clinic_id:
        config = (
            ReminderProviderConfig.objects.filter(clinic_id=clinic_id).only("sms_provider").first()
        )
        if config:
            return str(config.sms_provider).lower()
    return str(getattr(settings, "REMINDER_SMS_PROVIDER", "internal")).lower()


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
