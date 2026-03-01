from django.db import models

from apps.tenancy.models import Clinic


class Client(models.Model):
    """
    Global owner (person). Can belong to 0..N clinics.
    Address fields are required for prescriptions.
    """

    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)

    phone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)

    # ---- Address (for prescriptions & documents) ----
    street = models.CharField(max_length=255, blank=True)
    house_number = models.CharField(max_length=32, blank=True)
    apartment = models.CharField(max_length=32, blank=True)
    city = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=100, blank=True, default="Polska")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def full_address(self) -> str:
        """
        Human-readable address, useful for prescriptions / PDFs.
        """
        parts = [
            f"{self.street} {self.house_number}".strip(),
            f"Apt {self.apartment}" if self.apartment else "",
            f"{self.postal_code} {self.city}".strip(),
            self.country,
        ]
        return ", ".join(p for p in parts if p)


class ClientClinic(models.Model):
    """
    Membership linking Client <-> Clinic.
    """

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="client_memberships",
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
