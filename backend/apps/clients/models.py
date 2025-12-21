from django.db import models
from apps.tenancy.models import Clinic

class Client(models.Model):
    clinic = models.ForeignKey(Clinic, on_delete=models.PROTECT, related_name="clients")
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"
