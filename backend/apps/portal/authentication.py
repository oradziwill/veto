from __future__ import annotations

from rest_framework import authentication

from .tokens import decode_portal_access_token


class PortalPrincipal:
    """Fake request.user for client-portal JWT (not a staff User)."""

    is_authenticated = True
    is_portal = True

    def __init__(self, client_id: int, clinic_id: int):
        self.id = client_id
        self.client_id = client_id
        self.portal_clinic_id = clinic_id


class PortalJWTAuthentication(authentication.BaseAuthentication):
    """
    Accepts Bearer tokens issued by /api/portal/auth/confirm-code/ (audience=portal).
    Runs before SimpleJWT so staff access tokens (no aud) are ignored here.
    """

    www_authenticate_realm = "portal"

    def authenticate_header(self, request):
        # Required so DRF returns 401 (NotAuthenticated) instead of 403 when
        # IsAuthenticated fails — get_authenticate_header() uses only the
        # first configured authenticator (see rest_framework.views.APIView).
        return f'Bearer realm="{self.www_authenticate_realm}"'

    def authenticate(self, request):
        header = authentication.get_authorization_header(request)
        if not header or not header.startswith(b"Bearer "):
            return None
        raw = header[7:].decode("utf-8").strip()
        if not raw:
            return None
        try:
            payload = decode_portal_access_token(raw)
        except Exception:
            return None
        client_id = int(payload["client_id"])
        clinic_id = int(payload["clinic_id"])
        principal = PortalPrincipal(client_id=client_id, clinic_id=clinic_id)
        return principal, raw
