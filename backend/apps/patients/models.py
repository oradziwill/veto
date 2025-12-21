from django.db import models
from apps.tenancy.models import Clinic
from apps.clients.models import Client
from apps.accounts.models import User


class Patient(models.Model):
    """
    Animal (pet). Belongs to exactly one clinic.
    Owner is a global Client.
    """
    clinic = models.ForeignKey(
        Clinic, on_delete=models.PROTECT, related_name="patients"
    )
    owner = models.ForeignKey(
        Client, on_delete=models.PROTECT, related_name="patients"
    )

    name = models.CharField(max_length=120)
    species = models.CharField(max_length=80)
    breed = models.CharField(max_length=120, blank=True)
    sex = models.CharField(max_length=16, blank=True)
    birth_date = models.DateField(null=True, blank=True)

    microchip_no = models.CharField(max_length=64, blank=True)
    allergies = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    primary_vet = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_patients",
        limit_choices_to={"is_vet": True},
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.species})"
