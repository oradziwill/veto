from django.conf import settings
from django.db import models

from apps.tenancy.models import Clinic


class AuditLog(models.Model):
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    request_id = models.CharField(max_length=64, blank=True)
    action = models.CharField(max_length=64)
    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=64)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["clinic", "created_at"],
                name="audit_audlo_clinic__5fce9d_idx",
            ),
            models.Index(
                fields=["clinic", "action"],
                name="audit_audlo_clinic__ad06da_idx",
            ),
            models.Index(
                fields=["clinic", "entity_type", "entity_id"],
                name="audit_audlo_clinic__406f18_idx",
            ),
        ]

    def __str__(self):
        return f"AuditLog({self.action} {self.entity_type}:{self.entity_id})"
