from django.db import models

from apps.tenancy.models import Clinic


class ClinicWorkingHours(models.Model):
    """
    Defines when the clinic is open — per weekday.
    Weekday follows Python convention: Monday=0 ... Sunday=6.
    If a weekday has no active entry, the clinic is considered closed that day.
    """

    class Weekday(models.IntegerChoices):
        MON = 0, "Monday"
        TUE = 1, "Tuesday"
        WED = 2, "Wednesday"
        THU = 3, "Thursday"
        FRI = 4, "Friday"
        SAT = 5, "Saturday"
        SUN = 6, "Sunday"

    clinic = models.ForeignKey(
        Clinic, on_delete=models.CASCADE, related_name="working_hours"
    )
    weekday = models.IntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    # If set, the open time is split into shifts of this many hours.
    # e.g. open 08:00-20:00 with shift_hours=6 → shifts 08-14, 14-20.
    # Null means the entire open period is treated as one shift.
    shift_hours = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Duty shift length in hours. Leave blank for a single shift covering the full open period.",
    )

    class Meta:
        unique_together = ("clinic", "weekday")
        ordering = ["weekday"]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.end_time and self.start_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "end_time must be after start_time"})

    def __str__(self):
        return f"{self.clinic} {self.get_weekday_display()} {self.start_time}-{self.end_time}"
