"""Billing API serializers. Totals are calculated, never accepted."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from billing.balances import (
    invoice_allocated,
    invoice_outstanding,
    invoice_total,
    payment_allocated,
    payment_refunded,
    payment_unallocated,
)
from billing.models import Allocation, Invoice, Payment, Refund
from common.api.scope import reject_client_scope
from common.money import MoneyFormatError, money_to_api_string, parse_money
from organizations.models import Workspace


def _workspace(context: Mapping[str, Any]) -> Workspace:
    workspace = context.get("workspace")
    if not isinstance(workspace, Workspace):
        raise serializers.ValidationError("The active workspace is missing.")
    return workspace


def _raw(serializer: serializers.BaseSerializer[Any], key: str, value: str) -> object:
    initial = getattr(serializer, "initial_data", None)
    if isinstance(initial, dict) and key in initial:
        return initial[key]
    return value


def _money(value: str, raw: object) -> Decimal:
    if isinstance(raw, (float, bool)):
        raise serializers.ValidationError("Enter an amount as a decimal string.")
    try:
        return parse_money(value)
    except MoneyFormatError as exc:
        raise serializers.ValidationError(str(exc)) from exc


class InvoiceLineWriteSerializer(serializers.Serializer[dict[str, Any]]):
    description = serializers.CharField(max_length=200)
    quantity = serializers.CharField()
    unit_amount = serializers.CharField()

    def validate_quantity(self, value: str) -> Decimal:
        amount = _money(value, _raw(self, "quantity", value))
        if amount <= 0:
            raise serializers.ValidationError("Enter a quantity greater than zero.")
        return amount

    def validate_unit_amount(self, value: str) -> Decimal:
        amount = _money(value, _raw(self, "unit_amount", value))
        if amount <= 0:
            raise serializers.ValidationError("Enter an amount greater than zero.")
        return amount


class InvoiceWriteSerializer(serializers.Serializer[dict[str, Any]]):
    resident_id = serializers.UUIDField()
    tenancy_id = serializers.UUIDField(required=False, allow_null=True)
    booking_id = serializers.UUIDField(required=False, allow_null=True)
    issued_on = serializers.DateField()
    due_on = serializers.DateField()
    from_tenancy = serializers.BooleanField(required=False, default=False)
    include_deposit = serializers.BooleanField(required=False, default=False)
    lines = InvoiceLineWriteSerializer(many=True, required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        reject_client_scope(self.initial_data, _workspace(self.context), creating=True)
        if isinstance(self.initial_data, dict):
            blocked = {
                "reference",
                "status",
                "currency_code",
                "total",
                "total_amount",
                "outstanding",
                "outstanding_amount",
                "balance",
                "recorded_by",
            }
            present = blocked.intersection(self.initial_data)
            if present:
                field = sorted(present)[0]
                raise serializers.ValidationError(
                    {field: "The server calculates this. Do not send it."}
                )
        if attrs.get("include_deposit") and not attrs.get("from_tenancy"):
            raise serializers.ValidationError(
                {"include_deposit": "A deposit line comes from the agreement fee."}
            )
        return attrs


class VoidSerializer(serializers.Serializer[dict[str, Any]]):
    reason = serializers.CharField(max_length=200)
    voided_on = serializers.DateField()

    def validate_reason(self, value: str) -> str:
        reason = value.strip()
        if not reason:
            raise serializers.ValidationError("Enter a reason.")
        return reason


class PaymentWriteSerializer(serializers.Serializer[dict[str, Any]]):
    resident_id = serializers.UUIDField()
    amount = serializers.CharField()
    paid_on = serializers.DateField()
    method = serializers.ChoiceField(choices=Payment.Method.choices)
    external_reference = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=80,
    )

    def validate_amount(self, value: str) -> Decimal:
        amount = _money(value, _raw(self, "amount", value))
        if amount <= 0:
            raise serializers.ValidationError("Enter an amount greater than zero.")
        return amount

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        reject_client_scope(self.initial_data, _workspace(self.context), creating=True)
        if isinstance(self.initial_data, dict):
            calculated = (
                "reference",
                "status",
                "currency_code",
                "unallocated",
                "balance",
            )
            for field in calculated:
                if field in self.initial_data:
                    raise serializers.ValidationError(
                        {field: "The server calculates this. Do not send it."}
                    )
            reserved = ("provider", "provider_reference", "provider_status")
            for field in reserved:
                if field in self.initial_data:
                    raise serializers.ValidationError(
                        {
                            field: (
                                "The server records a provider payment. Do not send it."
                            )
                        }
                    )
        return attrs


class AllocationWriteSerializer(serializers.Serializer[dict[str, Any]]):
    payment_id = serializers.UUIDField()
    invoice_id = serializers.UUIDField()
    amount = serializers.CharField()

    def validate_amount(self, value: str) -> Decimal:
        amount = _money(value, _raw(self, "amount", value))
        if amount <= 0:
            raise serializers.ValidationError("Enter an amount greater than zero.")
        return amount

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        reject_client_scope(self.initial_data, _workspace(self.context), creating=True)
        return attrs


class ReversalSerializer(serializers.Serializer[dict[str, Any]]):
    reason = serializers.CharField(max_length=200)
    reversed_on = serializers.DateField()

    def validate_reason(self, value: str) -> str:
        reason = value.strip()
        if not reason:
            raise serializers.ValidationError("Enter a reason.")
        return reason


class RefundWriteSerializer(serializers.Serializer[dict[str, Any]]):
    amount = serializers.CharField()
    refunded_on = serializers.DateField()
    reason = serializers.CharField(max_length=200)
    external_reference = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=80,
    )

    def validate_amount(self, value: str) -> Decimal:
        amount = _money(value, _raw(self, "amount", value))
        if amount <= 0:
            raise serializers.ValidationError("Enter an amount greater than zero.")
        return amount

    def validate_reason(self, value: str) -> str:
        reason = value.strip()
        if not reason:
            raise serializers.ValidationError("Enter a reason.")
        return reason

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        reject_client_scope(self.initial_data, _workspace(self.context), creating=True)
        return attrs


class InvoiceSerializer(serializers.ModelSerializer[Invoice]):
    resident_id = serializers.UUIDField(read_only=True)
    resident_name = serializers.SerializerMethodField()
    tenancy_id = serializers.UUIDField(read_only=True, allow_null=True)
    lines = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    allocated_amount = serializers.SerializerMethodField()
    outstanding_amount = serializers.SerializerMethodField()
    void_reason = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = (
            "id",
            "reference",
            "resident_id",
            "resident_name",
            "tenancy_id",
            "issued_on",
            "due_on",
            "currency_code",
            "status",
            "lines",
            "total_amount",
            "allocated_amount",
            "outstanding_amount",
            "void_reason",
        )
        read_only_fields = fields

    def get_resident_name(self, obj: Invoice) -> str:
        return obj.resident.display_name

    def get_lines(self, obj: Invoice) -> list[dict[str, str]]:
        return [
            {
                "description": line.description,
                "quantity": money_to_api_string(line.quantity),
                "unit_amount": money_to_api_string(line.unit_amount),
                "line_total": money_to_api_string(line.line_total),
            }
            for line in obj.lines.all()
        ]

    def get_total_amount(self, obj: Invoice) -> str:
        return money_to_api_string(invoice_total(obj))

    def get_allocated_amount(self, obj: Invoice) -> str:
        return money_to_api_string(invoice_allocated(obj))

    def get_outstanding_amount(self, obj: Invoice) -> str:
        return money_to_api_string(invoice_outstanding(obj))

    def get_void_reason(self, obj: Invoice) -> str | None:
        try:
            return obj.void_record.reason
        except ObjectDoesNotExist:
            return None


class PaymentSerializer(serializers.ModelSerializer[Payment]):
    resident_id = serializers.UUIDField(read_only=True)
    resident_name = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    recorded_by_email = serializers.SerializerMethodField()
    allocated_amount = serializers.SerializerMethodField()
    refunded_amount = serializers.SerializerMethodField()
    unallocated_amount = serializers.SerializerMethodField()
    allocations = serializers.SerializerMethodField()
    refunds = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            "id",
            "reference",
            "resident_id",
            "resident_name",
            "amount",
            "currency_code",
            "paid_on",
            "method",
            "external_reference",
            "provider",
            "provider_reference",
            "provider_status",
            "status",
            "recorded_by_email",
            "allocated_amount",
            "refunded_amount",
            "unallocated_amount",
            "allocations",
            "refunds",
        )
        read_only_fields = fields

    def get_resident_name(self, obj: Payment) -> str:
        return obj.resident.display_name

    def get_amount(self, obj: Payment) -> str:
        return money_to_api_string(obj.amount)

    def get_recorded_by_email(self, obj: Payment) -> str:
        user = obj.recorded_by
        if user is None:
            return ""
        return user.email

    def get_allocated_amount(self, obj: Payment) -> str:
        return money_to_api_string(payment_allocated(obj))

    def get_refunded_amount(self, obj: Payment) -> str:
        return money_to_api_string(payment_refunded(obj))

    def get_unallocated_amount(self, obj: Payment) -> str:
        return money_to_api_string(payment_unallocated(obj))

    def get_allocations(self, obj: Payment) -> list[dict[str, str | bool]]:
        rows: list[dict[str, str | bool]] = []
        for allocation in obj.allocations.all():
            reversed_row = _reversed(allocation)
            rows.append(
                {
                    "id": str(allocation.id),
                    "invoice_id": str(allocation.invoice_id),
                    "invoice_reference": allocation.invoice.reference,
                    "amount": money_to_api_string(allocation.amount),
                    "reversed": reversed_row,
                }
            )
        return rows

    def get_refunds(self, obj: Payment) -> list[dict[str, str]]:
        return [
            {
                "id": str(refund.id),
                "amount": money_to_api_string(refund.amount),
                "refunded_on": refund.refunded_on.isoformat(),
                "reason": refund.reason,
                "external_reference": refund.external_reference,
            }
            for refund in obj.refunds.all()
        ]


class AllocationSerializer(serializers.ModelSerializer[Allocation]):
    payment_id = serializers.UUIDField(read_only=True)
    invoice_id = serializers.UUIDField(read_only=True)
    invoice_reference = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    reversed = serializers.SerializerMethodField()

    class Meta:
        model = Allocation
        fields = (
            "id",
            "payment_id",
            "invoice_id",
            "invoice_reference",
            "amount",
            "reversed",
        )
        read_only_fields = fields

    def get_invoice_reference(self, obj: Allocation) -> str:
        return obj.invoice.reference

    def get_amount(self, obj: Allocation) -> str:
        return money_to_api_string(obj.amount)

    def get_reversed(self, obj: Allocation) -> bool:
        return _reversed(obj)


class RefundSerializer(serializers.ModelSerializer[Refund]):
    payment_id = serializers.UUIDField(read_only=True)
    amount = serializers.SerializerMethodField()

    class Meta:
        model = Refund
        fields = (
            "id",
            "payment_id",
            "amount",
            "currency_code",
            "refunded_on",
            "reason",
            "external_reference",
        )
        read_only_fields = fields

    def get_amount(self, obj: Refund) -> str:
        return money_to_api_string(obj.amount)


def _reversed(allocation: Allocation) -> bool:
    try:
        reversal = allocation.reversal
    except ObjectDoesNotExist:
        return False
    return reversal is not None
