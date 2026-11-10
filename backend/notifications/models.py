"""Email notices. SMS is a seam only until a provider is chosen."""

from __future__ import annotations

import uuid

from django.db import models


class Delivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="notification_deliveries",
    )
    kind = models.CharField(max_length=40)
    dedupe_key = models.CharField(max_length=80)
    recipient = models.EmailField()
    subject = models.CharField(max_length=120)
    body = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "dedupe_key"],
                name="notice_once_per_workspace",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.kind
