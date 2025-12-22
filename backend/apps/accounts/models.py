from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.tenancy.models import Clinic


class User(AbstractUser):
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
    )
    is_vet = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.username
