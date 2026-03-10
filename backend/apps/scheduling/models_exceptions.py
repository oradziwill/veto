from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.tenancy.models import Clinic


class VetAvailabilityException(models.Model):
    """
    One-off override for a specific vet and date.
    - day off: is_day_off=True
    - custom hours: is_day_off=False and start_time/end_time set
    """

    clinic = models.ForeignKey(Clinic, on_delete=models.PROTECT, related_name="vet_exceptions")
    vet = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="availability_exceptions",
        limit_choices_to={"is_vet": True},
    )
    date = models.DateField()

    is_day_off = models.BooleanField(default=False)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    note = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("clinic", "vet", "date")
        ordering = ["-date", "vet_id"]

    def clean(self):
        # If not day off, either both times are set or neither (meaning "no override")
        if not self.is_day_off:
            if (self.start_time is None) ^ (self.end_time is None):
                raise models.ValidationError("Provide both start_time and end_time or neither.")
            if self.start_time and self.end_time and self.end_time <= self.start_time:
                raise models.ValidationError("end_time must be after start_time.")

    def __str__(self) -> str:
        if self.is_day_off:
            return f"{self.vet} day off ({self.date})"
        if self.start_time and self.end_time:
            return f"{self.vet} override {self.start_time}-{self.end_time} ({self.date})"
        return f"{self.vet} exception ({self.date})"
