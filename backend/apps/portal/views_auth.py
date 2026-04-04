from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.clients.models import ClientClinic

from .models import PortalLoginChallenge
from .services.confirm_lockout import (
    clear_portal_confirm_failures,
    is_portal_confirm_blocked,
    record_portal_confirm_failure,
)
from .services.magic_link_tokens import digest_magic_token, generate_magic_link_plaintext
from .services.otp_email import send_portal_otp_email, sendgrid_configured
from .services.rate_limit import (
    client_ip_from_request,
    portal_confirm_ip_key,
    portal_confirm_mailbox_key,
    portal_magic_link_ip_key,
    portal_request_code_ip_key,
    portal_request_code_mailbox_key,
    rate_limit_exceeded,
)
from .tokens import create_portal_access_token
from .view_helpers import generate_portal_code, public_clinic_or_404

logger = logging.getLogger(__name__)


class PortalAuthRequestCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        slug = (request.data.get("clinic_slug") or "").strip()
        email = (request.data.get("email") or "").strip().lower()
        if not slug or not email:
            return Response(
                {"detail": "clinic_slug and email are required."},
                status=400,
            )
        ip = client_ip_from_request(request)
        if rate_limit_exceeded(
            portal_request_code_ip_key(ip),
            int(getattr(settings, "PORTAL_OTP_REQUEST_LIMIT_PER_IP", 60)),
            int(getattr(settings, "PORTAL_OTP_REQUEST_IP_WINDOW_SEC", 3600)),
        ):
            return Response(
                {"detail": "Too many requests. Please try again later."},
                status=429,
            )
        if rate_limit_exceeded(
            portal_request_code_mailbox_key(slug, email),
            int(getattr(settings, "PORTAL_OTP_REQUEST_LIMIT_PER_MAILBOX", 10)),
            int(getattr(settings, "PORTAL_OTP_REQUEST_MAILBOX_WINDOW_SEC", 900)),
        ):
            return Response(
                {"detail": "Too many requests. Please try again later."},
                status=429,
            )

        err, clinic = public_clinic_or_404(slug)
        if err:
            return err

        membership = (
            ClientClinic.objects.filter(
                clinic=clinic,
                is_active=True,
                client__email__iexact=email,
            )
            .select_related("client")
            .first()
        )

        generic = {"detail": "If this email is registered at the clinic, a login code was sent."}
        if not membership:
            return Response(generic, status=200)

        code = generate_portal_code()
        magic_plain = generate_magic_link_plaintext()
        magic_digest = digest_magic_token(magic_plain)
        link_template = str(getattr(settings, "PORTAL_MAGIC_LINK_URL_TEMPLATE", "") or "").strip()
        magic_url = (
            link_template.replace("{token}", magic_plain) if "{token}" in link_template else None
        )

        PortalLoginChallenge.objects.create(
            clinic=clinic,
            client=membership.client,
            code_hash=make_password(code),
            magic_token_digest=magic_digest,
            expires_at=timezone.now()
            + timedelta(minutes=int(getattr(settings, "PORTAL_OTP_EXPIRE_MINUTES", 15))),
        )

        if getattr(settings, "PORTAL_OTP_EMAIL_ENABLED", False):
            if sendgrid_configured():
                try:
                    send_portal_otp_email(
                        to_email=membership.client.email,
                        code=code,
                        clinic_name=clinic.name,
                        magic_link_url=magic_url,
                        magic_plain_token=magic_plain if not magic_url else None,
                    )
                except Exception:
                    logger.exception(
                        "portal_otp_email_send_failed clinic_id=%s client_id=%s",
                        clinic.id,
                        membership.client_id,
                    )
            else:
                logger.warning(
                    "PORTAL_OTP_EMAIL_ENABLED but SendGrid is not configured "
                    "(set REMINDER_SENDGRID_API_KEY and REMINDER_SENDGRID_FROM_EMAIL)."
                )

        payload = dict(generic)
        if getattr(settings, "PORTAL_RETURN_OTP_IN_RESPONSE", False):
            payload["_dev_otp"] = code
            payload["_dev_magic_link_token"] = magic_plain
        return Response(payload, status=200)


class PortalAuthMagicLinkView(APIView):
    """
    POST /api/portal/auth/magic-link/
    Body: { "token": "<plaintext from email or dev response>" } → same access JWT as confirm-code.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        token = (request.data.get("token") or "").strip()
        if not token:
            return Response({"detail": "token is required."}, status=400)

        ip = client_ip_from_request(request)
        if rate_limit_exceeded(
            portal_magic_link_ip_key(ip),
            int(getattr(settings, "PORTAL_MAGIC_LINK_LIMIT_PER_IP", 60)),
            int(getattr(settings, "PORTAL_MAGIC_LINK_IP_WINDOW_SEC", 900)),
        ):
            return Response(
                {"detail": "Too many requests. Please try again later."},
                status=429,
            )

        digest = digest_magic_token(token)
        now = timezone.now()
        err_resp: Response | None = None
        consumed_challenge: PortalLoginChallenge | None = None
        with transaction.atomic():
            ch = (
                PortalLoginChallenge.objects.select_for_update()
                .filter(
                    magic_token_digest=digest,
                    consumed_at__isnull=True,
                    expires_at__gte=now,
                )
                .select_related("clinic", "client")
                .first()
            )
            if not ch:
                err_resp = Response(
                    {"detail": "Invalid or expired sign-in link."},
                    status=400,
                )
            elif not ch.clinic.online_booking_enabled:
                err_resp = Response(
                    {"detail": "Online booking is disabled for this clinic."},
                    status=403,
                )
            elif not ClientClinic.objects.filter(
                clinic=ch.clinic,
                client=ch.client,
                is_active=True,
            ).exists():
                err_resp = Response(
                    {"detail": "Invalid or expired sign-in link."},
                    status=400,
                )
            else:
                ch.consumed_at = now
                ch.save(update_fields=["consumed_at"])
                consumed_challenge = ch

        if err_resp is not None:
            return err_resp
        assert consumed_challenge is not None
        clear_portal_confirm_failures(
            consumed_challenge.clinic.slug,
            (consumed_challenge.client.email or "").strip().lower(),
            ip,
        )
        access = create_portal_access_token(
            client_id=consumed_challenge.client_id,
            clinic_id=consumed_challenge.clinic_id,
        )
        return Response({"access": access})


class PortalAuthConfirmCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        slug = (request.data.get("clinic_slug") or "").strip()
        email = (request.data.get("email") or "").strip().lower()
        code = (request.data.get("code") or "").strip()
        if not slug or not email or not code:
            return Response(
                {"detail": "clinic_slug, email, and code are required."},
                status=400,
            )
        ip = client_ip_from_request(request)
        if is_portal_confirm_blocked(slug, email, ip):
            return Response(
                {"detail": "Too many invalid code attempts. Please try again later."},
                status=429,
            )
        if rate_limit_exceeded(
            portal_confirm_ip_key(ip),
            int(getattr(settings, "PORTAL_OTP_CONFIRM_LIMIT_PER_IP", 80)),
            int(getattr(settings, "PORTAL_OTP_CONFIRM_IP_WINDOW_SEC", 900)),
        ):
            return Response(
                {"detail": "Too many requests. Please try again later."},
                status=429,
            )
        if rate_limit_exceeded(
            portal_confirm_mailbox_key(slug, email),
            int(getattr(settings, "PORTAL_OTP_CONFIRM_LIMIT_PER_MAILBOX", 30)),
            int(getattr(settings, "PORTAL_OTP_CONFIRM_MAILBOX_WINDOW_SEC", 900)),
        ):
            return Response(
                {"detail": "Too many requests. Please try again later."},
                status=429,
            )

        err, clinic = public_clinic_or_404(slug)
        if err:
            return err

        membership = (
            ClientClinic.objects.filter(
                clinic=clinic,
                is_active=True,
                client__email__iexact=email,
            )
            .select_related("client")
            .first()
        )
        if not membership:
            return Response({"detail": "Invalid or expired code."}, status=400)

        now = timezone.now()
        challenge = (
            PortalLoginChallenge.objects.filter(
                clinic=clinic,
                client=membership.client,
                consumed_at__isnull=True,
                expires_at__gte=now,
            )
            .order_by("-created_at")
            .first()
        )
        if not challenge or not check_password(code, challenge.code_hash):
            record_portal_confirm_failure(slug, email, ip)
            return Response({"detail": "Invalid or expired code."}, status=400)

        challenge.consumed_at = now
        challenge.save(update_fields=["consumed_at"])
        clear_portal_confirm_failures(slug, email, ip)

        access = create_portal_access_token(
            client_id=membership.client_id,
            clinic_id=clinic.id,
        )
        return Response({"access": access})
