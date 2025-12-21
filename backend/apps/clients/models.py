from django.db import models
from apps.tenancy.models import Clinic


class Client(models.Model):
    """
    Global owner (person). Can belong to 0..N clinics.
    """
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class ClientClinic(models.Model):
    """
    Membership linking Client <-> Clinic.
    """
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="memberships"
    )
    clinic = models.ForeignKey(
        Clinic, on_delete=models.PROTECT, related_name="client_memberships"
    )

    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["client", "clinic"],
                name="uniq_client_per_clinic",
            )
        ]

    def __str__(self) -> str:
        return f"{self.client} @ {self.clinic}"
