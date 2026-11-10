"""Phase 02 rows. Imported by billing.models so Django registers them."""

from __future__ import annotations

import uuid
from typing import Any

from django.db import models
from django.db.models import Q

from common.money import money_amount_field


class RecurringCharge(models.Model):
    """One generated rent invoice for one agreement period.

    The pair of tenancy and period start is the idempotency key. A second
    run for the same period does not create another invoice.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.PROTECT,
        related_name="recurring_charges",
    )
    tenancy = models.ForeignKey(
        "tenancies.Tenancy",
        on_delete=models.PROTECT,
        related_name="recurring_charges",
    )
    period_start = models.DateField()
    invoice = models.OneToOneField(
        "billing.Invoice",
        on_delete=models.PROTECT,
        related_name="recurring_charge",
    )
    fee_amount = money_amount_field()
    fee_period = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenancy", "period_start"],
                name="recur_period_once",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.tenancy_id} {self.period_start}"


class BillingJobRun(models.Model):
    """One workspace-scoped run of a billing command. Counts only, no names."""

    class Kind(models.TextChoices):
        RECURRING = "recurring", "Recurring invoices"
        REMINDERS = "reminders", "Billing reminders"

    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="billing_job_runs",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    as_of = models.DateField()
    dry_run = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=Status.choices)
    created_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    detail = models.CharField(max_length=200, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.kind} {self.as_of}"


class PaymentAttempt(models.Model):
    """A checkout that is not yet a ledger payment."""

    class Channel(models.TextChoices):
        CARD = "card", "Card"
        MOBILE_MONEY = "mobile_money", "Mobile money"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.PROTECT,
        related_name="payment_attempts",
    )
    invoice = models.ForeignKey(
        "billing.Invoice",
        on_delete=models.PROTECT,
        related_name="payment_attempts",
    )
    resident = models.ForeignKey(
        "residents.Resident",
        on_delete=models.PROTECT,
        related_name="payment_attempts",
    )
    reference = models.CharField(max_length=64, unique=True)
    amount = money_amount_field()
    amount_minor = models.PositiveIntegerField()
    currency_code = models.CharField(max_length=3)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    authorization_url = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(channel__in=["card", "mobile_money"]),
                name="attempt_channel_known",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["pending", "success", "failed", "rejected"]),
                name="attempt_status_known",
            ),
        ]

    def __str__(self) -> str:
        return self.reference


class ProviderEvent(models.Model):
    """One provider notification. Replays hit the unique event id."""

    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        REJECTED = "rejected", "Rejected"
        IGNORED = "ignored", "Ignored"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=32)
    provider_event_id = models.CharField(max_length=80)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="provider_events",
    )
    status = models.CharField(max_length=16, choices=Status.choices)
    safe_detail = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_event_id"],
                name="provider_event_once",
            ),
        ]

    def save(self, **kwargs: Any) -> None:
        self.safe_detail = self.safe_detail[:200]
        super().save(**kwargs)

    def __str__(self) -> str:
        return f"{self.provider} {self.provider_event_id}"
