"""A reservation. The occupied space lives on the assignment, not here."""

from __future__ import annotations

import uuid
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Booking(models.Model):
    """A confirmed reservation that can be cancelled or converted to a tenancy.

    Statuses: `confirmed` holds a space, `converted` became an agreement, and
    `cancelled` releases the space. Rows are kept after those changes.
    """

    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        CONVERTED = "converted", "Converted"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    resident = models.ForeignKey(
        "residents.Resident",
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.CONFIRMED,
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["confirmed", "converted", "cancelled"]),
                name="book_status_known",
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")),
                name="book_end_inclusive",
            ),
        ]

    def __str__(self) -> str:
        return f"Booking {self.start_date}"

    def clean(self) -> None:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValidationError(
                {
                    "end_date": (
                        "The end date is the last occupied day and "
                        "cannot be before the start date."
                    )
                }
            )
        if self.resident.workspace_id != self.workspace_id:
            raise ValidationError({"resident": "Choose a resident in this workspace."})

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)
