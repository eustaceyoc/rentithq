"""Maintenance API serializers. The server sets the reference and the status."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from rest_framework import serializers

from common.api.scope import reject_client_scope
from common.money import MoneyFormatError, money_to_api_string, parse_money
from maintenance.models import MaintenanceRequest, MaintenanceUpdate
from organizations.models import Workspace
from properties.models import Space


def _workspace(context: Mapping[str, Any]) -> Workspace:
    workspace = context.get("workspace")
    if not isinstance(workspace, Workspace):
        raise serializers.ValidationError("The active workspace is missing.")
    return workspace


def _money(raw: object) -> Decimal:
    if isinstance(raw, (float, bool)):
        raise serializers.ValidationError("Enter an amount as a decimal string.")
    try:
        amount = parse_money(raw)
    except MoneyFormatError as exc:
        raise serializers.ValidationError(str(exc)) from exc
    if amount < 0:
        raise serializers.ValidationError("Enter a cost that is zero or greater.")
    return amount


class MaintenanceUpdateSerializer(serializers.ModelSerializer[MaintenanceUpdate]):
    actor_email = serializers.SerializerMethodField()
    cost_amount = serializers.SerializerMethodField()
    assignee_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = MaintenanceUpdate
        fields = (
            "id",
            "status_before",
            "status_after",
            "note",
            "cost_amount",
            "assignee_id",
            "actor_email",
            "created_at",
        )
        read_only_fields = fields

    def get_actor_email(self, obj: MaintenanceUpdate) -> str:
        if obj.actor_id is None or obj.actor is None:
            return ""
        return obj.actor.email

    def get_cost_amount(self, obj: MaintenanceUpdate) -> str | None:
        if obj.cost_amount is None:
            return None
        return money_to_api_string(obj.cost_amount)


class MaintenanceRequestSerializer(serializers.ModelSerializer[MaintenanceRequest]):
    workspace_id = serializers.UUIDField(read_only=True)
    property_id = serializers.UUIDField(read_only=True, allow_null=True)
    space_id = serializers.UUIDField(read_only=True, allow_null=True)
    bed_id = serializers.UUIDField(read_only=True, allow_null=True)
    resident_id = serializers.UUIDField(read_only=True, allow_null=True)
    assignee_id = serializers.UUIDField(read_only=True, allow_null=True)
    property_name = serializers.SerializerMethodField()
    space_name = serializers.SerializerMethodField()
    bed_name = serializers.SerializerMethodField()
    resident_name = serializers.SerializerMethodField()
    assignee_email = serializers.SerializerMethodField()
    reported_by_email = serializers.SerializerMethodField()
    cost_amount = serializers.SerializerMethodField()
    location_blocked = serializers.SerializerMethodField()
    updates = MaintenanceUpdateSerializer(many=True, read_only=True)

    class Meta:
        model = MaintenanceRequest
        fields = (
            "id",
            "workspace_id",
            "reference",
            "property_id",
            "property_name",
            "space_id",
            "space_name",
            "bed_id",
            "bed_name",
            "resident_id",
            "resident_name",
            "description",
            "priority",
            "status",
            "completion_note",
            "cost_amount",
            "currency_code",
            "assignee_id",
            "assignee_email",
            "reported_by_email",
            "location_blocked",
            "updates",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_property_name(self, obj: MaintenanceRequest) -> str:
        if obj.property_id is None or obj.property is None:
            return ""
        return obj.property.name

    def get_space_name(self, obj: MaintenanceRequest) -> str:
        if obj.space_id is None or obj.space is None:
            return ""
        return obj.space.name

    def get_bed_name(self, obj: MaintenanceRequest) -> str:
        if obj.bed_id is None or obj.bed is None:
            return ""
        return obj.bed.name

    def get_resident_name(self, obj: MaintenanceRequest) -> str:
        if obj.resident_id is None or obj.resident is None:
            return ""
        return obj.resident.display_name

    def get_assignee_email(self, obj: MaintenanceRequest) -> str:
        if obj.assignee_id is None or obj.assignee is None:
            return ""
        return obj.assignee.email

    def get_reported_by_email(self, obj: MaintenanceRequest) -> str:
        if obj.reported_by_id is None or obj.reported_by is None:
            return ""
        return obj.reported_by.email

    def get_cost_amount(self, obj: MaintenanceRequest) -> str | None:
        if obj.cost_amount is None:
            return None
        return money_to_api_string(obj.cost_amount)

    def get_location_blocked(self, obj: MaintenanceRequest) -> bool:
        """True when the named place is already unavailable for maintenance.

        Filing or completing a request does not change that block.
        """
        bed = obj.bed
        if (
            bed is not None
            and bed.availability == Space.Availability.UNAVAILABLE
            and bed.block_reason == "maintenance"
        ):
            return True
        if obj.space_id is not None and obj.space is not None:
            return (
                obj.space.availability == Space.Availability.UNAVAILABLE
                and obj.space.block_reason == "maintenance"
            )
        return False


class _PlaceMixin(serializers.Serializer[dict[str, Any]]):
    def _reject_attachments(self) -> None:
        initial = self.initial_data
        if not isinstance(initial, dict):
            return
        for key in (
            "photo",
            "photos",
            "attachment",
            "attachments",
            "file",
            "document",
        ):
            if key in initial:
                raise serializers.ValidationError(
                    {key: "Attachments are not available yet."}
                )


class MaintenanceCreateSerializer(_PlaceMixin):
    property_id = serializers.UUIDField(required=False, allow_null=True)
    space_id = serializers.UUIDField(required=False, allow_null=True)
    bed_id = serializers.UUIDField(required=False, allow_null=True)
    resident_id = serializers.UUIDField(required=False, allow_null=True)
    assignee_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(max_length=4000)
    priority = serializers.ChoiceField(choices=MaintenanceRequest.Priority.choices)
    cost_amount = serializers.JSONField(required=False)
    status = serializers.CharField(required=False)
    completion_note = serializers.CharField(required=False, allow_blank=True)

    def validate_description(self, value: str) -> str:
        text = value.strip()
        if not text:
            raise serializers.ValidationError("Describe the problem.")
        return text

    def validate_cost_amount(self, value: object) -> Decimal:
        return _money(value)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        reject_client_scope(
            self.initial_data,
            _workspace(self.context),
            creating=True,
        )
        self._reject_attachments()
        initial = self.initial_data
        if isinstance(initial, dict):
            for key in ("reference", "currency_code", "location_blocked"):
                if key in initial:
                    raise serializers.ValidationError(
                        {key: "The server sets this field."}
                    )
        return attrs


class MaintenanceUpdateWriteSerializer(_PlaceMixin):
    description = serializers.CharField(max_length=4000, required=False)
    priority = serializers.ChoiceField(
        choices=MaintenanceRequest.Priority.choices,
        required=False,
    )
    status = serializers.ChoiceField(
        choices=MaintenanceRequest.Status.choices,
        required=False,
    )
    assignee_id = serializers.UUIDField(required=False, allow_null=True)
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    completion_note = serializers.CharField(
        max_length=2000,
        required=False,
        allow_blank=True,
    )
    cost_amount = serializers.JSONField(required=False)

    def validate_description(self, value: str) -> str:
        text = value.strip()
        if not text:
            raise serializers.ValidationError("Describe the problem.")
        return text

    def validate_cost_amount(self, value: object) -> Decimal:
        return _money(value)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        reject_client_scope(
            self.initial_data,
            _workspace(self.context),
            creating=False,
        )
        self._reject_attachments()
        initial = self.initial_data
        if isinstance(initial, dict):
            for key in (
                "reference",
                "currency_code",
                "location_blocked",
                "property_id",
                "space_id",
                "bed_id",
                "resident_id",
            ):
                if key in initial:
                    raise serializers.ValidationError(
                        {key: "This field cannot be changed."}
                    )
        if not attrs:
            raise serializers.ValidationError("Provide a field to change.")
        return attrs
