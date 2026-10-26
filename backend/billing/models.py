"""Invoices, payments, allocations, and the records that correct them.

Outstanding amounts are not stored. A void, reversal, or refund is its own
row. Issued lines and recorded payments are not edited in place.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from common.money import MONEY_QUANTUM, money_amount_field


def _currency_shape() -> Q:
    return Q(currency_code__regex=r"^[A-Z]{3}$")


class DocumentCounter(models.Model):
    """One row per workspace. Locked while a reference number is taken."""

    workspace = models.OneToOneField(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="billing_counter",
    )
    next_invoice = models.PositiveIntegerField(default=1)
    next_payment = models.PositiveIntegerField(default=1)

    def __str__(self) -> str:
        return f"Numbers for {self.workspace_id}"


class Invoice(models.Model):
    """A charge issued to one resident. The total is the sum of its lines."""

    class Status(models.TextChoices):
        ISSUED = "issued", "Issued"
        VOID = "void", "Void"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    resident = models.ForeignKey(
        "residents.Resident",
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    tenancy = models.ForeignKey(
        "tenancies.Tenancy",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    reference = models.CharField(max_length=32)
    issued_on = models.DateField()
    due_on = models.DateField()
    currency_code = models.CharField(max_length=3)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ISSUED,
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoices_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issued_on", "reference"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "reference"],
                name="inv_reference_unique",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["issued", "void"]),
                name="inv_status_known",
            ),
            models.CheckConstraint(
                condition=Q(due_on__gte=F("issued_on")),
                name="inv_due_after_issue",
            ),
            models.CheckConstraint(
                condition=_currency_shape(),
                name="inv_currency_shape",
            ),
        ]

    def __str__(self) -> str:
        return self.reference

    def clean(self) -> None:
        if self.due_on < self.issued_on:
            raise ValidationError(
                {"due_on": "The due date cannot be before the invoice date."}
            )
        if self.resident.workspace_id != self.workspace_id:
            raise ValidationError({"resident": "Choose a resident in this workspace."})
        if self.tenancy_id is not None:
            tenancy = self.tenancy
            if tenancy is None or tenancy.workspace_id != self.workspace_id:
                raise ValidationError(
                    {"tenancy": "Choose an agreement in this workspace."}
                )
            if tenancy.resident_id != self.resident_id:
                raise ValidationError(
                    {"tenancy": "Choose an agreement for this resident."}
                )
        if self.currency_code != self.workspace.currency_code:
            raise ValidationError({"currency_code": "Use the workspace currency."})

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)


class InvoiceLine(models.Model):
    """One calculated charge. The client does not send the line total."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="lines",
    )
    position = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=19, decimal_places=4)
    unit_amount = money_amount_field()
    line_total = money_amount_field(help_text="quantity times unit amount.")

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["invoice", "position"],
                name="inv_line_position_unique",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="inv_line_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_amount__gt=0),
                name="inv_line_unit_positive",
            ),
            models.CheckConstraint(
                condition=Q(line_total__gte=0),
                name="inv_line_total_nonneg",
            ),
        ]

    def __str__(self) -> str:
        return self.description

    def clean(self) -> None:
        description = self.description.strip()
        if not description:
            raise ValidationError({"description": "Enter a description."})
        self.description = description
        if self.quantity <= 0:
            raise ValidationError({"quantity": "Enter a quantity greater than zero."})
        if self.unit_amount <= 0:
            raise ValidationError({"unit_amount": "Enter an amount greater than zero."})
        expected = (self.quantity * self.unit_amount).quantize(MONEY_QUANTUM)
        if self.line_total != expected:
            raise ValidationError({"line_total": "The line total is calculated."})

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)


class InvoiceVoid(models.Model):
    """The record that withdraws an issued invoice. The lines stay."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.PROTECT,
        related_name="void_record",
    )
    reason = models.CharField(max_length=200)
    voided_on = models.DateField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoice_voids_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Void {self.invoice_id}"

    def clean(self) -> None:
        reason = self.reason.strip()
        if not reason:
            raise ValidationError({"reason": "Enter a reason."})
        self.reason = reason

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)


def _optional_token(value: str | None) -> str | None:
    if value is None:
        return None
    token = value.strip()
    return token or None


class Payment(models.Model):
    """Money the workspace received.

    A manual row leaves the provider fields empty. A later gateway row can
    store the provider name, its reference, and its status on this same record.
    """

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        MOBILE_MONEY = "mobile_money", "Mobile money"
        CARD = "card", "Card"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        RECORDED = "recorded", "Recorded"
        VOID = "void", "Void"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    resident = models.ForeignKey(
        "residents.Resident",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    reference = models.CharField(max_length=32)
    amount = money_amount_field()
    currency_code = models.CharField(max_length=3)
    paid_on = models.DateField()
    method = models.CharField(max_length=32, choices=Method.choices)
    external_reference = models.CharField(max_length=80, blank=True, default="")
    provider = models.CharField(max_length=32, null=True, blank=True)
    provider_reference = models.CharField(max_length=80, null=True, blank=True)
    provider_status = models.CharField(max_length=32, null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.RECORDED,
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payments_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-paid_on", "reference"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "reference"],
                name="pay_reference_unique",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["recorded", "void"]),
                name="pay_status_known",
            ),
            models.CheckConstraint(
                condition=Q(
                    method__in=[
                        "cash",
                        "bank_transfer",
                        "mobile_money",
                        "card",
                        "other",
                    ]
                ),
                name="pay_method_known",
            ),
            models.CheckConstraint(
                condition=(
                    Q(provider__isnull=True, provider_reference__isnull=True)
                    | (
                        Q(provider__isnull=False)
                        & ~Q(provider="")
                        & Q(provider_reference__isnull=False)
                        & ~Q(provider_reference="")
                    )
                ),
                name="pay_provider_pair",
            ),
            models.CheckConstraint(
                condition=(
                    Q(provider_status__isnull=True)
                    | (Q(provider__isnull=False) & ~Q(provider_status=""))
                ),
                name="pay_provider_status_with_provider",
            ),
            models.UniqueConstraint(
                fields=["workspace", "provider", "provider_reference"],
                condition=Q(provider_reference__isnull=False),
                name="pay_provider_reference_unique",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="pay_amount_positive",
            ),
            models.CheckConstraint(
                condition=_currency_shape(),
                name="pay_currency_shape",
            ),
        ]

    def __str__(self) -> str:
        return self.reference

    def clean(self) -> None:
        if self.amount <= 0:
            raise ValidationError({"amount": "Enter an amount greater than zero."})
        if self.resident.workspace_id != self.workspace_id:
            raise ValidationError({"resident": "Choose a resident in this workspace."})
        if self.currency_code != self.workspace.currency_code:
            raise ValidationError({"currency_code": "Use the workspace currency."})
        self.external_reference = self.external_reference.strip()
        self.provider = _optional_token(self.provider)
        self.provider_reference = _optional_token(self.provider_reference)
        self.provider_status = _optional_token(self.provider_status)
        if self.provider is not None:
            self.provider = self.provider.lower()
        if (self.provider is None) != (self.provider_reference is None):
            raise ValidationError(
                {
                    "provider": (
                        "A provider payment needs both a provider and a reference."
                    )
                }
            )
        if self.provider_status is not None and self.provider is None:
            raise ValidationError(
                {"provider_status": "A provider status needs a provider."}
            )

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)


class PaymentVoid(models.Model):
    """Withdraws a payment that was never applied or refunded."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        related_name="void_record",
    )
    reason = models.CharField(max_length=200)
    voided_on = models.DateField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payment_voids_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Void {self.payment_id}"

    def clean(self) -> None:
        reason = self.reason.strip()
        if not reason:
            raise ValidationError({"reason": "Enter a reason."})
        self.reason = reason

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)


class Allocation(models.Model):
    """How much of one payment applies to one invoice. The row is kept."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    amount = money_amount_field()
    currency_code = models.CharField(max_length=3)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="allocations_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="alloc_amount_positive",
            ),
            models.CheckConstraint(
                condition=_currency_shape(),
                name="alloc_currency_shape",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.amount} to {self.invoice_id}"

    def clean(self) -> None:
        if self.amount <= 0:
            raise ValidationError({"amount": "Enter an amount greater than zero."})
        if self.payment.workspace_id != self.workspace_id:
            raise ValidationError({"payment": "Choose a payment in this workspace."})
        if self.invoice.workspace_id != self.workspace_id:
            raise ValidationError({"invoice": "Choose an invoice in this workspace."})
        if self.payment.resident_id != self.invoice.resident_id:
            raise ValidationError(
                {"invoice": "The payment and the invoice are for different residents."}
            )
        if (
            self.currency_code != self.payment.currency_code
            or self.currency_code != self.invoice.currency_code
        ):
            raise ValidationError(
                {
                    "currency_code": (
                        "The payment and the invoice use different currencies."
                    )
                }
            )

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)


class AllocationReversal(models.Model):
    """Puts an allocation's amount back on the payment and the invoice."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    allocation = models.OneToOneField(
        Allocation,
        on_delete=models.PROTECT,
        related_name="reversal",
    )
    reason = models.CharField(max_length=200)
    reversed_on = models.DateField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="allocation_reversals_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Reversal {self.allocation_id}"

    def clean(self) -> None:
        reason = self.reason.strip()
        if not reason:
            raise ValidationError({"reason": "Enter a reason."})
        self.reason = reason

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)


class Refund(models.Model):
    """Money returned from the unallocated part of a payment."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.PROTECT,
        related_name="refunds",
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="refunds",
    )
    amount = money_amount_field()
    currency_code = models.CharField(max_length=3)
    refunded_on = models.DateField()
    reason = models.CharField(max_length=200)
    external_reference = models.CharField(max_length=80, blank=True, default="")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="refunds_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["refunded_on", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="refund_amount_positive",
            ),
            models.CheckConstraint(
                condition=_currency_shape(),
                name="refund_currency_shape",
            ),
        ]

    def __str__(self) -> str:
        return f"Refund {self.amount}"

    def clean(self) -> None:
        reason = self.reason.strip()
        if not reason:
            raise ValidationError({"reason": "Enter a reason."})
        self.reason = reason
        self.external_reference = self.external_reference.strip()
        if self.amount <= 0:
            raise ValidationError({"amount": "Enter an amount greater than zero."})
        if self.payment.workspace_id != self.workspace_id:
            raise ValidationError({"payment": "Choose a payment in this workspace."})
        if self.currency_code != self.payment.currency_code:
            raise ValidationError({"currency_code": "Use the payment currency."})

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)
