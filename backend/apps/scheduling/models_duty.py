from django.conf import settings
from django.db import models

from apps.tenancy.models import Clinic


class DutyAssignment(models.Model):
    """
    A doctor assigned to cover the clinic on a specific date.
    Multiple doctors can be assigned per day (e.g. morning + afternoon shifts).
    """

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="duty_assignments")
    vet = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="duty_assignments",
        limit_choices_to={"role": "doctor"},
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_auto_generated = models.BooleanField(default=False)
    note = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "start_time"]
        indexes = [
            models.Index(fields=["clinic", "date"]),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.end_time and self.start_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "end_time must be after start_time"})

    def __str__(self):
        return f"{self.vet} on duty {self.date} {self.start_time}-{self.end_time}"
