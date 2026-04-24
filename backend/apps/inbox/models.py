from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class InboxTask(models.Model):
    class TaskType(models.TextChoices):
        PHONE_CALLBACK = "phone_callback", "Oddzwonienie"
        SIGN_DOCUMENT = "sign_document", "Do podpisu"
        CHECK_RESULT = "check_result", "Sprawdź wynik"
        OTHER = "other", "Inne"

    class Status(models.TextChoices):
        OPEN = "open", "Otwarte"
        IN_PROGRESS = "in_progress", "W toku"
        CLOSED = "closed", "Zamknięte"

    clinic = models.ForeignKey(
        "tenancy.Clinic",
        on_delete=models.CASCADE,
        related_name="inbox_tasks",
    )
    vet = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inbox_tasks",
    )
    task_type = models.CharField(max_length=30, choices=TaskType.choices, default=TaskType.OTHER)
    patient_name = models.CharField(max_length=200, blank=True)
    note = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="inbox_tasks_created",
    )
    created_at = models.DateTimeField(default=timezone.now)

    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inbox_tasks_closed",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    close_comment = models.TextField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "-created_at"]

    def __str__(self):
        return f"[{self.get_status_display()}] {self.get_task_type_display()} → {self.vet}"
