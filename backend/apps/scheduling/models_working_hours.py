from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class VetWorkingHours(models.Model):
    """
    Working hours per vet and weekday.
    Weekday follows Python convention: Monday=0 ... Sunday=6.
    """

    class Weekday(models.IntegerChoices):
        MON = 0, "Monday"
        TUE = 1, "Tuesday"
        WED = 2, "Wednesday"
        THU = 3, "Thursday"
        FRI = 4, "Friday"
        SAT = 5, "Saturday"
        SUN = 6, "Sunday"

    vet = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="working_hours",
        limit_choices_to={"is_vet": True},
    )
    weekday = models.IntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("vet", "weekday", "start_time", "end_time")
        ordering = ["vet_id", "weekday", "start_time"]

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError({"end_time": "end_time must be after start_time"})

    def __str__(self) -> str:
        return f"{self.vet} {self.get_weekday_display()} {self.start_time}-{self.end_time}"
