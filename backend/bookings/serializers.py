"""Booking API serializers."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from rest_framework import serializers

from bookings.models import Booking
from common.api.scope import reject_client_scope
from common.money import MoneyFormatError, parse_money
from organizations.models import Workspace
from tenancies.models import Assignment


def _workspace(context: Mapping[str, Any]) -> Workspace:
    workspace = context.get("workspace")
    if not isinstance(workspace, Workspace):
        raise serializers.ValidationError("The active workspace is missing.")
    return workspace


def _money(value: str, raw: object) -> Decimal:
    if isinstance(raw, (float, bool)):
        raise serializers.ValidationError("Enter an amount as a decimal string.")
    try:
        amount = parse_money(value)
    except MoneyFormatError as exc:
        raise serializers.ValidationError(str(exc)) from exc
    if amount < 0:
        raise serializers.ValidationError("Enter a zero or positive amount.")
    return amount


class BookingSerializer(serializers.ModelSerializer[Booking]):
    workspace_id = serializers.UUIDField(read_only=True)
    resident_id = serializers.UUIDField(read_only=True)
    resident_name = serializers.SerializerMethodField()
    assignment_id = serializers.SerializerMethodField()
    space_id = serializers.SerializerMethodField()
    bed_id = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = (
            "id",
            "workspace_id",
            "resident_id",
            "resident_name",
            "status",
            "start_date",
            "end_date",
            "assignment_id",
            "space_id",
            "bed_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def _open_stay(self, obj: Booking) -> Assignment | None:
        cache: dict[str, Assignment | None] | None = getattr(self, "_stay_cache", None)
        if cache is None:
            cache = {}
            self._stay_cache = cache
        key = str(obj.id)
        if key not in cache:
            cache[key] = (
                obj.assignments.filter(
                    status__in=(
                        Assignment.Status.CONFIRMED,
                        Assignment.Status.ACTIVE,
                    )
                )
                .order_by("-start_date", "id")
                .first()
            )
        return cache[key]

    def get_resident_name(self, obj: Booking) -> str:
        return obj.resident.display_name

    def get_assignment_id(self, obj: Booking) -> str | None:
        stay = self._open_stay(obj)
        if stay is None:
            return None
        return str(stay.id)

    def get_space_id(self, obj: Booking) -> str | None:
        stay = self._open_stay(obj)
        if stay is None:
            return None
        return str(stay.space_id)

    def get_bed_id(self, obj: Booking) -> str | None:
        stay = self._open_stay(obj)
        if stay is None or stay.bed_id is None:
            return None
        return str(stay.bed_id)


class BookingWriteSerializer(serializers.Serializer[dict[str, Any]]):
    resident_id = serializers.UUIDField(required=False)
    space_id = serializers.UUIDField(required=False)
    bed_id = serializers.UUIDField(required=False, allow_null=True)
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
                {"status": "Use cancel or convert to change a reservation."}
            )
        if not self.creating and not attrs:
            raise serializers.ValidationError("Provide a field to change.")
        return attrs


class BookingConvertSerializer(serializers.Serializer[dict[str, Any]]):
    fee_amount = serializers.CharField()
    fee_period = serializers.ChoiceField(choices=("night", "week", "month"))
    deposit_amount = serializers.CharField(required=False, allow_blank=False)
    check_in = serializers.BooleanField(required=False, default=False)

    def validate_fee_amount(self, value: str) -> Decimal:
        raw = (
            self.initial_data.get("fee_amount")
            if isinstance(self.initial_data, dict)
            else value
        )
        return _money(value, raw)

    def validate_deposit_amount(self, value: str) -> Decimal:
        raw = (
            self.initial_data.get("deposit_amount")
            if isinstance(self.initial_data, dict)
            else value
        )
        return _money(value, raw)
