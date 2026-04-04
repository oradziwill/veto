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


class PortalIdempotencyRecord(models.Model):
    """
    Stores portal POST responses for ``Idempotency-Key`` replay (booking / payments).
    Scoped per owner client, clinic, operation label, and key.
    """

    client_id = models.PositiveIntegerField()
    clinic_id = models.PositiveIntegerField()
    operation = models.CharField(max_length=96)
    idempotency_key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    response_status = models.SmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["client_id", "clinic_id", "operation", "idempotency_key"],
                name="portal_idem_client_clinic_op_key_uniq",
            )
        ]
        indexes = [
            models.Index(
                fields=["client_id", "clinic_id", "-created_at"],
                name="portal_pid_client_clinic_crt",
            ),
        ]

    def __str__(self) -> str:
        return f"PortalIdempotency({self.operation!r}, key={self.idempotency_key[:16]!r}…)"
