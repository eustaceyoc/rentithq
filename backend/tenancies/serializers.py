"""Tenancy and assignment API serializers."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from rest_framework import serializers

from common.api.scope import reject_client_scope
from common.money import MoneyFormatError, money_to_api_string, parse_money
from organizations.models import Workspace
from tenancies.models import Assignment, Tenancy


def _workspace(context: Mapping[str, Any]) -> Workspace:
    workspace = context.get("workspace")
    if not isinstance(workspace, Workspace):
        raise serializers.ValidationError("The active workspace is missing.")
    return workspace


def parse_amount(value: str, raw: object) -> Decimal:
    if isinstance(raw, (float, bool)):
        raise serializers.ValidationError("Enter an amount as a decimal string.")
    try:
        amount = parse_money(value)
    except MoneyFormatError as exc:
        raise serializers.ValidationError(str(exc)) from exc
    if amount < 0:
        raise serializers.ValidationError("Enter a zero or positive amount.")
    return amount


class TenancySerializer(serializers.ModelSerializer[Tenancy]):
    workspace_id = serializers.UUIDField(read_only=True)
    resident_id = serializers.UUIDField(read_only=True)
    booking_id = serializers.UUIDField(read_only=True, allow_null=True)
    resident_name = serializers.SerializerMethodField()
    fee_amount = serializers.SerializerMethodField()
    deposit_amount = serializers.SerializerMethodField()

    class Meta:
        model = Tenancy
        fields = (
            "id",
            "workspace_id",
            "resident_id",
            "resident_name",
            "booking_id",
            "status",
            "start_date",
            "end_date",
            "ended_on",
            "fee_amount",
            "fee_period",
            "deposit_amount",
            "currency_code",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_resident_name(self, obj: Tenancy) -> str:
        return obj.resident.display_name

    def get_fee_amount(self, obj: Tenancy) -> str:
        return money_to_api_string(obj.fee_amount)

    def get_deposit_amount(self, obj: Tenancy) -> str:
        return money_to_api_string(obj.deposit_amount)


class TenancyWriteSerializer(serializers.Serializer[dict[str, Any]]):
    resident_id = serializers.UUIDField(required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False, allow_null=True)
    fee_amount = serializers.CharField(required=False)
    fee_period = serializers.ChoiceField(
        choices=("night", "week", "month"),
        required=False,
    )
    deposit_amount = serializers.CharField(required=False)
    space_id = serializers.UUIDField(required=False, allow_null=True)
    bed_id = serializers.UUIDField(required=False, allow_null=True)
    check_in = serializers.BooleanField(required=False, default=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.creating = bool(kwargs.pop("creating", False))
        super().__init__(*args, **kwargs)
        if self.creating:
            self.fields["resident_id"].required = True
            self.fields["start_date"].required = True
            self.fields["fee_amount"].required = True
            self.fields["fee_period"].required = True

    def validate_fee_amount(self, value: str) -> Decimal:
        raw = (
            self.initial_data.get("fee_amount")
            if isinstance(self.initial_data, dict)
            else value
        )
        return parse_amount(value, raw)

    def validate_deposit_amount(self, value: str) -> Decimal:
        raw = (
            self.initial_data.get("deposit_amount")
            if isinstance(self.initial_data, dict)
            else value
        )
        return parse_amount(value, raw)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        reject_client_scope(
            self.initial_data,
            _workspace(self.context),
            creating=self.creating,
        )
        if isinstance(self.initial_data, dict):
            if "status" in self.initial_data or "currency_code" in self.initial_data:
                raise serializers.ValidationError(
                    {"status": "Status and currency are chosen by the server."}
                )
            if not self.creating and (
                "space_id" in self.initial_data or "resident_id" in self.initial_data
            ):
                raise serializers.ValidationError(
                    {
                        "space_id": (
                            "Move a stay with transfer. "
                            "The agreement keeps its resident."
                        )
                    }
                )
        if not self.creating and not attrs:
            raise serializers.ValidationError("Provide a field to change.")
        return attrs


class EndTenancySerializer(serializers.Serializer[dict[str, Any]]):
    ended_on = serializers.DateField()


class AssignmentSerializer(serializers.ModelSerializer[Assignment]):
    workspace_id = serializers.UUIDField(read_only=True)
    resident_id = serializers.UUIDField(read_only=True)
    space_id = serializers.UUIDField(read_only=True)
    bed_id = serializers.UUIDField(read_only=True, allow_null=True)
    booking_id = serializers.UUIDField(read_only=True, allow_null=True)
    tenancy_id = serializers.UUIDField(read_only=True, allow_null=True)
    transferred_from_id = serializers.UUIDField(read_only=True, allow_null=True)
    resident_name = serializers.SerializerMethodField()
    space_name = serializers.SerializerMethodField()
    bed_name = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = (
            "id",
            "workspace_id",
            "resident_id",
            "resident_name",
            "space_id",
            "space_name",
            "bed_id",
            "bed_name",
            "booking_id",
            "tenancy_id",
            "transferred_from_id",
            "status",
            "start_date",
            "end_date",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_resident_name(self, obj: Assignment) -> str:
        return obj.resident.display_name

    def get_space_name(self, obj: Assignment) -> str:
        return obj.space.name

    def get_bed_name(self, obj: Assignment) -> str | None:
        if obj.bed_id is None or obj.bed is None:
            return None
        return obj.bed.name


class AssignmentWriteSerializer(serializers.Serializer[dict[str, Any]]):
    resident_id = serializers.UUIDField(required=False)
    space_id = serializers.UUIDField(required=False)
    bed_id = serializers.UUIDField(required=False, allow_null=True)
    tenancy_id = serializers.UUIDField(required=False, allow_null=True)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False, allow_null=True)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.creating = bool(kwargs.pop("creating", False))
        super().__init__(*args, **kwargs)
        if self.creating:
            self.fields["resident_id"].required = True
            self.fields["space_id"].required = True
            self.fields["start_date"].required = True

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        reject_client_scope(
            self.initial_data,
            _workspace(self.context),
            creating=self.creating,
        )
        if isinstance(self.initial_data, dict) and "status" in self.initial_data:
            raise serializers.ValidationError(
                {
                    "status": (
                        "Use check-in, check-out, cancel, or transfer to change a stay."
                    )
                }
            )
        if not self.creating and not attrs:
            raise serializers.ValidationError("Provide a field to change.")
        if not self.creating and (
            "space_id" in attrs or "bed_id" in attrs or "resident_id" in attrs
        ):
            raise serializers.ValidationError(
                {"space_id": "Use transfer to move a stay to another space."}
            )
        return attrs


class CheckOutSerializer(serializers.Serializer[dict[str, Any]]):
    end_date = serializers.DateField()


class TransferSerializer(serializers.Serializer[dict[str, Any]]):
    space_id = serializers.UUIDField()
    bed_id = serializers.UUIDField(required=False, allow_null=True)
    start_date = serializers.DateField()
