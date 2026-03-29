from __future__ import annotations

from datetime import timedelta

import jwt
from django.conf import settings
from django.utils import timezone

PORTAL_JWT_AUDIENCE = "portal"


def create_portal_access_token(*, client_id: int, clinic_id: int) -> str:
    lifetime = getattr(settings, "PORTAL_ACCESS_TOKEN_LIFETIME", timedelta(hours=24))
    exp = timezone.now() + lifetime
    payload = {
        "client_id": client_id,
        "clinic_id": clinic_id,
        "aud": PORTAL_JWT_AUDIENCE,
        "exp": exp,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_portal_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=["HS256"],
        audience=PORTAL_JWT_AUDIENCE,
    )
