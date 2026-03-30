from django.db import models

from apps.clients.models import Client
from apps.tenancy.models import Clinic


class PortalLoginChallenge(models.Model):
    """
    One-time code for owner (Client) login to the booking portal.
    Code is stored hashed; plaintext is never persisted.
    """

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="portal_login_challenges",
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="portal_login_challenges",
    )
    code_hash = models.CharField(max_length=255)
    magic_token_digest = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="SHA-256 hex digest of one-time magic link token (empty for legacy rows).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["clinic", "client", "-created_at"],
                name="portal_plc_clinic_crt_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"PortalLoginChallenge(clinic={self.clinic_id}, client={self.client_id})"
