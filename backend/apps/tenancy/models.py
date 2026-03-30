from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils.text import slugify


class Clinic(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    address = models.CharField(max_length=512, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)

    # Polish tax identifier (10 digits, no dashes)
    nip = models.CharField(max_length=10, blank=True)
    # KSeF token for invoice submission (stored encrypted in production)
    ksef_token = models.CharField(max_length=512, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    online_booking_enabled = models.BooleanField(
        default=True,
        help_text="Allow pet owners to request appointments via the public booking portal.",
    )
    portal_booking_deposit_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        help_text="If > 0, portal bookings create a draft deposit invoice; visit stays scheduled until paid.",
    )
    portal_booking_deposit_line_label = models.CharField(
        max_length=255,
        default="Online booking deposit",
        blank=True,
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:200] or "clinic"
            slug = base
            i = 2
            while Clinic.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class ClinicHoliday(models.Model):
    """
    One-day clinic closure (e.g. holiday / renovation / emergency).
    If active, availability returns no slots for that date.
    """

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="holidays")
    date = models.DateField()
    reason = models.CharField(max_length=255, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("clinic", "date")
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["clinic", "date"]),
        ]

    def __str__(self) -> str:
        extra = f" ({self.reason})" if self.reason else ""
        return f"{self.clinic} closed on {self.date}{extra}"
