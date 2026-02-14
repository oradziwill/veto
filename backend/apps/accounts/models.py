from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.tenancy.models import Clinic


class User(AbstractUser):
    class Role(models.TextChoices):
        DOCTOR = "doctor", "Doctor"
        RECEPTIONIST = "receptionist", "Receptionist"
        ADMIN = "admin", "Clinic Admin"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
    )
    is_vet = models.BooleanField(default=False)  # Deprecated: use role. Kept for migration/backward compat.
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.RECEPTIONIST,
    )

    def __str__(self) -> str:
        return self.username

    @property
    def is_doctor(self) -> bool:
        return self.role == self.Role.DOCTOR

    @property
    def is_receptionist(self) -> bool:
        return self.role == self.Role.RECEPTIONIST

    @property
    def is_clinic_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    @property
    def can_perform_clinical_actions(self) -> bool:
        """Doctor and Admin can perform clinical exams, close visits, medical records, etc."""
        return self.role in (self.Role.DOCTOR, self.Role.ADMIN)
