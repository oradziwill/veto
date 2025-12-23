from __future__ import annotations

from django.db import models
from django.utils.text import slugify


class Clinic(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    address = models.CharField(max_length=512, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

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
