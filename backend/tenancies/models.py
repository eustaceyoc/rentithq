"""Agreements and the stays that occupy a unit, room, or bed."""

from __future__ import annotations

import uuid
from typing import Any

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from common.money import money_amount_field


class Tenancy(models.Model):
    """Commercial terms for one resident. Not an invoice and not a room.

    `end_date` is the expected last day. `ended_on` is set when the agreement
    ends. Fee and deposit amounts are the agreed figures, in the workspace
    currency copied at creation. They are not a balance.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"
        CANCELLED = "cancelled", "Cancelled"

    class FeePeriod(models.TextChoices):
        NIGHT = "night", "Night"
        WEEK = "week", "Week"
        MONTH = "month", "Month"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="tenancies",
    )
    resident = models.ForeignKey(
        "residents.Resident",
        on_delete=models.PROTECT,
        related_name="tenancies",
    )
    booking = models.OneToOneField(
        "bookings.Booking",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="tenancy",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    ended_on = models.DateField(null=True, blank=True)
    fee_amount = money_amount_field(help_text="Agreed charge for one fee period.")
    fee_period = models.CharField(max_length=16, choices=FeePeriod.choices)
    deposit_amount = money_amount_field(
        help_text="Agreed deposit. Not a ledger balance."
    )
    currency_code = models.CharField(max_length=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["active", "ended", "cancelled"]),
                name="ten_status_known",
            ),
            models.CheckConstraint(
                condition=Q(fee_period__in=["night", "week", "month"]),
                name="ten_fee_period_known",
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")),
                name="ten_end_inclusive",
            ),
            models.CheckConstraint(
                condition=~Q(status="ended") | Q(ended_on__isnull=False),
                name="ten_ended_has_date",
            ),
            models.CheckConstraint(
                condition=Q(fee_amount__gte=0),
                name="ten_fee_nonneg",
            ),
            models.CheckConstraint(
                condition=Q(deposit_amount__gte=0),
                name="ten_deposit_nonneg",
            ),
        ]

    def __str__(self) -> str:
        return f"Tenancy {self.start_date}"

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
        if self.status == self.Status.ENDED and self.ended_on is None:
            raise ValidationError({"ended_on": "Enter the day the agreement ended."})
        if self.resident.workspace_id != self.workspace_id:
            raise ValidationError({"resident": "Choose a resident in this workspace."})
        if self.booking_id is not None:
            booking = self.booking
            if booking is None or booking.workspace_id != self.workspace_id:
                raise ValidationError(
                    {"booking": "Choose a booking in this workspace."}
                )

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)


class Assignment(models.Model):
    """One stay in a unit, a whole room, or a bed.

    The end date is inclusive: it is the last occupied day, and the space is
    free the next day. A null end is open-ended. Confirmed and active rows
    block the space. Checked-out, cancelled, and transferred rows stay as
    history and do not block. A transfer adds a new row; it does not rewrite
    the old room onto the old row.
    """

    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        ACTIVE = "active", "Active"
        CHECKED_OUT = "checked_out", "Checked out"
        CANCELLED = "cancelled", "Cancelled"
        TRANSFERRED = "transferred", "Transferred"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    resident = models.ForeignKey(
        "residents.Resident",
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    space = models.ForeignKey(
        "properties.Space",
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    bed = models.ForeignKey(
        "properties.Bed",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    booking = models.ForeignKey(
        "bookings.Booking",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    tenancy = models.ForeignKey(
        Tenancy,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    transferred_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transfers",
    )
    status = models.CharField(max_length=16, choices=Status.choices)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "confirmed",
                        "active",
                        "checked_out",
                        "cancelled",
                        "transferred",
                    ]
                ),
                name="asg_status_known",
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")),
                name="asg_end_inclusive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.status} {self.start_date}"

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
        if self.space.workspace_id != self.workspace_id:
            raise ValidationError({"space": "Choose a space in this workspace."})
        if self.bed_id is not None:
            bed = self.bed
            if bed is None or bed.workspace_id != self.workspace_id:
                raise ValidationError({"bed": "Choose a bed in this workspace."})
            if bed.space_id != self.space_id:
                raise ValidationError({"bed": "Choose a bed in this room."})
            if self.space.kind != "room":
                raise ValidationError({"bed": "A whole unit does not have beds."})
        if self.booking_id is not None:
            booking = self.booking
            if booking is None or booking.workspace_id != self.workspace_id:
                raise ValidationError(
                    {"booking": "Choose a booking in this workspace."}
                )
        if self.tenancy_id is not None:
            tenancy = self.tenancy
            if tenancy is None or tenancy.workspace_id != self.workspace_id:
                raise ValidationError(
                    {"tenancy": "Choose an agreement in this workspace."}
                )

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)


class OccupancyBlock(models.Model):
    """Derived hold used by the database to reject overlapping stays.

    A row exists only while its assignment is confirmed or active. A bed stay
    writes one bed row. A whole-room stay writes one room row and one row per
    bed, so a bed and its room cannot both be occupied. A whole unit writes
    one unit row. History lives on the assignment; these rows are replaced
    when the stay changes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="blocks",
    )
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="occupancy_blocks",
    )
    space = models.ForeignKey(
        "properties.Space",
        on_delete=models.CASCADE,
        related_name="occupancy_blocks",
    )
    bed = models.ForeignKey(
        "properties.Bed",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="occupancy_blocks",
    )
    period = DateRangeField()

    class Meta:
        constraints = [
            ExclusionConstraint(
                name="block_bed_no_overlap",
                expressions=[
                    ("bed", RangeOperators.EQUAL),
                    ("period", RangeOperators.OVERLAPS),
                ],
                condition=Q(bed__isnull=False),
            ),
            ExclusionConstraint(
                name="block_space_no_overlap",
                expressions=[
                    ("space", RangeOperators.EQUAL),
                    ("period", RangeOperators.OVERLAPS),
                ],
                condition=Q(bed__isnull=True),
            ),
        ]

    def __str__(self) -> str:
        return f"Hold {self.period}"
