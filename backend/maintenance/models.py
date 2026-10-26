"""Work orders. Status history is its own rows. There are no attachments."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from common.money import money_amount_field


def _currency_shape() -> Q:
    return Q(currency_code__regex=r"^[A-Z]{3}$")


class RequestCounter(models.Model):
    """One row per workspace. Locked while a reference number is taken."""

    workspace = models.OneToOneField(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="maintenance_counter",
    )
    next_number = models.PositiveIntegerField(default=1)

    def __str__(self) -> str:
        return f"Maintenance numbers for {self.workspace_id}"


class MaintenanceRequest(models.Model):
    """A request on a property, a space, a bed, or with no place yet."""

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ASSIGNED = "assigned", "Assigned"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.PROTECT,
        related_name="maintenance_requests",
    )
    property = models.ForeignKey(
        "properties.Property",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="maintenance_requests",
    )
    space = models.ForeignKey(
        "properties.Space",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="maintenance_requests",
    )
    bed = models.ForeignKey(
        "properties.Bed",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="maintenance_requests",
    )
    resident = models.ForeignKey(
        "residents.Resident",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="maintenance_requests",
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="maintenance_requests_reported",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="maintenance_requests_assigned",
    )
    reference = models.CharField(max_length=32)
    description = models.TextField()
    priority = models.CharField(max_length=16, choices=Priority.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
    )
    completion_note = models.TextField(blank=True, default="")
    cost_amount = money_amount_field(
        null=True,
        help_text="Latest recorded cost. Not an invoice.",
    )
    currency_code = models.CharField(max_length=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "reference"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "reference"],
                name="mnt_reference_unique",
            ),
            models.CheckConstraint(
                condition=Q(priority__in=["low", "normal", "high", "urgent"]),
                name="mnt_priority_known",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "open",
                        "assigned",
                        "in_progress",
                        "completed",
                        "cancelled",
                    ]
                ),
                name="mnt_status_known",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="open", assignee__isnull=True)
                    | Q(
                        status__in=["assigned", "in_progress", "completed"],
                        assignee__isnull=False,
                    )
                    | Q(status="cancelled")
                ),
                name="mnt_assignee_matches_status",
            ),
            models.CheckConstraint(
                condition=~Q(status="completed") | ~Q(completion_note=""),
                name="mnt_completed_has_note",
            ),
            models.CheckConstraint(
                condition=Q(bed__isnull=True) | Q(space__isnull=False),
                name="mnt_bed_needs_space",
            ),
            models.CheckConstraint(
                condition=Q(space__isnull=True) | Q(property__isnull=False),
                name="mnt_space_needs_property",
            ),
            models.CheckConstraint(
                condition=Q(cost_amount__isnull=True) | Q(cost_amount__gte=0),
                name="mnt_cost_non_negative",
            ),
            models.CheckConstraint(
                condition=_currency_shape(),
                name="mnt_currency_shape",
            ),
        ]
        indexes = [
            models.Index(
                fields=["workspace", "status"],
                name="mnt_ws_status",
            ),
        ]

    def __str__(self) -> str:
        return self.reference

    def clean(self) -> None:
        self.description = self.description.strip()
        self.completion_note = self.completion_note.strip()
        if not self.description:
            raise ValidationError({"description": "Describe the problem."})
        if self.priority not in self.Priority.values:
            raise ValidationError({"priority": "Choose a priority."})
        if self.status not in self.Status.values:
            raise ValidationError({"status": "Choose a status."})
        if self.currency_code != self.workspace.currency_code:
            raise ValidationError({"currency_code": "Use the workspace currency."})
        if self.cost_amount is not None and self.cost_amount < 0:
            raise ValidationError(
                {"cost_amount": "Enter a cost that is zero or greater."}
            )
        if self.status == self.Status.OPEN and self.assignee_id is not None:
            raise ValidationError({"assignee": "An open request has no assignee."})
        if (
            self.status
            in {
                self.Status.ASSIGNED,
                self.Status.IN_PROGRESS,
                self.Status.COMPLETED,
            }
            and self.assignee_id is None
        ):
            raise ValidationError({"assignee": "Choose an assignee."})
        if self.status == self.Status.COMPLETED and not self.completion_note:
            raise ValidationError({"completion_note": "Add a completion note."})
        self._clean_place()
        resident = self.resident
        if self.resident_id is not None and (
            resident is None or resident.workspace_id != self.workspace_id
        ):
            raise ValidationError({"resident": "Choose a resident in this workspace."})

    def _clean_place(self) -> None:
        chosen_property = self.property
        space = self.space
        bed = self.bed
        if self.property_id is not None and (
            chosen_property is None or chosen_property.workspace_id != self.workspace_id
        ):
            raise ValidationError({"property": "Choose a property in this workspace."})
        if self.space_id is not None and (
            self.property_id is None
            or space is None
            or space.property_id != self.property_id
            or space.workspace_id != self.workspace_id
        ):
            raise ValidationError({"space": "Choose a space on this property."})
        if self.bed_id is not None and (
            self.space_id is None
            or bed is None
            or bed.space_id != self.space_id
            or bed.workspace_id != self.workspace_id
        ):
            raise ValidationError({"bed": "Choose a bed in this space."})

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)


class MaintenanceUpdate(models.Model):
    """One row each time a request is filed or changed. This is the status history."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.PROTECT,
        related_name="maintenance_updates",
    )
    request = models.ForeignKey(
        MaintenanceRequest,
        on_delete=models.CASCADE,
        related_name="updates",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="maintenance_updates",
    )
    status_before = models.CharField(max_length=16, blank=True, default="")
    status_after = models.CharField(max_length=16)
    note = models.TextField(blank=True, default="")
    cost_amount = money_amount_field(null=True)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="maintenance_updates_assigned",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(cost_amount__isnull=True) | Q(cost_amount__gte=0),
                name="mnt_update_cost_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.status_before}->{self.status_after}"

    def clean(self) -> None:
        self.note = self.note.strip()
        if self.request.workspace_id != self.workspace_id:
            raise ValidationError(
                {"request": "The update must stay in the request's workspace."}
            )
        if self.cost_amount is not None and self.cost_amount < Decimal("0"):
            raise ValidationError(
                {"cost_amount": "Enter a cost that is zero or greater."}
            )

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)
