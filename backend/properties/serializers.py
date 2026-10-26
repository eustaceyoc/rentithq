"""Property API serializers. The workspace comes from the membership."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from rest_framework import serializers

from organizations.models import Workspace
from properties.models import Bed, Building, Floor, Property, Space
from properties.validation import block_pair_error


def _workspace(context: Mapping[str, Any]) -> Workspace:
    workspace = context.get("workspace")
    if not isinstance(workspace, Workspace):
        raise serializers.ValidationError("The active workspace is missing.")
    return workspace


def _reject_client_scope(
    initial: Any,
    workspace: Workspace,
    *,
    creating: bool,
) -> None:
    if not isinstance(initial, dict):
        return
    if "id" in initial:
        raise serializers.ValidationError({"id": "The client cannot choose this id."})
    if "is_staff" in initial or "is_superuser" in initial:
        raise serializers.ValidationError(
            {"is_staff": "This request cannot change platform access."}
        )
    for key in ("created_at", "updated_at", "workspace"):
        if key in initial:
            raise serializers.ValidationError({key: "This field cannot be changed."})
    if "workspace_id" not in initial:
        return
    if not creating:
        raise serializers.ValidationError(
            {"workspace_id": "The workspace cannot be changed."}
        )
    try:
        requested = uuid.UUID(str(initial["workspace_id"]))
    except ValueError as exc:
        raise serializers.ValidationError(
            {"workspace_id": "Choose the active workspace."}
        ) from exc
    if requested != workspace.id:
        raise serializers.ValidationError(
            {"workspace_id": ("A record can only be written in the active workspace.")}
        )


def _check_block(attrs: dict[str, Any]) -> None:
    if "availability" in attrs and "block_reason" in attrs:
        error = block_pair_error(str(attrs["availability"]), str(attrs["block_reason"]))
        if error:
            raise serializers.ValidationError(error)


class PropertySerializer(serializers.ModelSerializer[Property]):
    workspace_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Property
        fields = (
            "id",
            "workspace_id",
            "name",
            "address",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class PropertyWriteSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField(max_length=200, required=False)
    address = serializers.CharField(required=False, allow_blank=True)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.require_name = bool(kwargs.pop("require_name", False))
        super().__init__(*args, **kwargs)
        if self.require_name:
            self.fields["name"].required = True

    def validate_name(self, value: str) -> str:
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Enter a property name.")
        return name

    def validate_address(self, value: str) -> str:
        return value.strip()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        _reject_client_scope(
            self.initial_data,
            _workspace(self.context),
            creating=self.require_name,
        )
        if not self.require_name and not attrs:
            raise serializers.ValidationError("Provide a field to change.")
        return attrs


class BuildingSerializer(serializers.ModelSerializer[Building]):
    workspace_id = serializers.UUIDField(read_only=True)
    property_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Building
        fields = (
            "id",
            "workspace_id",
            "property_id",
            "name",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class BuildingWriteSerializer(serializers.Serializer[dict[str, Any]]):
    property_id = serializers.UUIDField(required=False)
    name = serializers.CharField(max_length=200, required=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.creating = bool(kwargs.pop("creating", False))
        super().__init__(*args, **kwargs)
        if self.creating:
            self.fields["property_id"].required = True
            self.fields["name"].required = True

    def validate_name(self, value: str) -> str:
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Enter a building name.")
        return name

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        _reject_client_scope(
            self.initial_data,
            _workspace(self.context),
            creating=self.creating,
        )
        if not self.creating and not attrs:
            raise serializers.ValidationError("Provide a field to change.")
        return attrs


class FloorSerializer(serializers.ModelSerializer[Floor]):
    workspace_id = serializers.UUIDField(read_only=True)
    property_id = serializers.UUIDField(read_only=True)
    building_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = Floor
        fields = (
            "id",
            "workspace_id",
            "property_id",
            "building_id",
            "name",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class FloorWriteSerializer(serializers.Serializer[dict[str, Any]]):
    property_id = serializers.UUIDField(required=False)
    building_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(max_length=200, required=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.creating = bool(kwargs.pop("creating", False))
        super().__init__(*args, **kwargs)
        if self.creating:
            self.fields["property_id"].required = True
            self.fields["name"].required = True

    def validate_name(self, value: str) -> str:
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Enter a floor name.")
        return name

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        _reject_client_scope(
            self.initial_data,
            _workspace(self.context),
            creating=self.creating,
        )
        if not self.creating and not attrs:
            raise serializers.ValidationError("Provide a field to change.")
        return attrs


class SpaceSerializer(serializers.ModelSerializer[Space]):
    workspace_id = serializers.UUIDField(read_only=True)
    property_id = serializers.UUIDField(read_only=True)
    building_id = serializers.UUIDField(read_only=True, allow_null=True)
    floor_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = Space
        fields = (
            "id",
            "workspace_id",
            "property_id",
            "building_id",
            "floor_id",
            "name",
            "kind",
            "availability",
            "block_reason",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SpaceWriteSerializer(serializers.Serializer[dict[str, Any]]):
    property_id = serializers.UUIDField(required=False)
    building_id = serializers.UUIDField(required=False, allow_null=True)
    floor_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(max_length=200, required=False)
    kind = serializers.ChoiceField(choices=Space.Kind.choices, required=False)
    availability = serializers.ChoiceField(
        choices=Space.Availability.choices,
        required=False,
    )
    block_reason = serializers.ChoiceField(
        choices=[("", "None"), ("maintenance", "Maintenance")],
        required=False,
        allow_blank=True,
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.creating = bool(kwargs.pop("creating", False))
        super().__init__(*args, **kwargs)
        if self.creating:
            self.fields["property_id"].required = True
            self.fields["name"].required = True
            self.fields["kind"].required = True

    def validate_name(self, value: str) -> str:
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Enter a name.")
        return name

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        _reject_client_scope(
            self.initial_data,
            _workspace(self.context),
            creating=self.creating,
        )
        if self.creating:
            attrs.setdefault("availability", Space.Availability.ACTIVE)
            attrs.setdefault("block_reason", "")
        _check_block(attrs)
        if not self.creating and not attrs:
            raise serializers.ValidationError("Provide a field to change.")
        return attrs


class BedSerializer(serializers.ModelSerializer[Bed]):
    workspace_id = serializers.UUIDField(read_only=True)
    space_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Bed
        fields = (
            "id",
            "workspace_id",
            "space_id",
            "name",
            "availability",
            "block_reason",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class BedWriteSerializer(serializers.Serializer[dict[str, Any]]):
    space_id = serializers.UUIDField(required=False)
    name = serializers.CharField(max_length=200, required=False)
    availability = serializers.ChoiceField(
        choices=Space.Availability.choices,
        required=False,
    )
    block_reason = serializers.ChoiceField(
        choices=[("", "None"), ("maintenance", "Maintenance")],
        required=False,
        allow_blank=True,
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.creating = bool(kwargs.pop("creating", False))
        super().__init__(*args, **kwargs)
        if self.creating:
            self.fields["space_id"].required = True
            self.fields["name"].required = True

    def validate_name(self, value: str) -> str:
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Enter a bed name.")
        return name

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        _reject_client_scope(
            self.initial_data,
            _workspace(self.context),
            creating=self.creating,
        )
        if self.creating:
            attrs.setdefault("availability", Space.Availability.ACTIVE)
            attrs.setdefault("block_reason", "")
        _check_block(attrs)
        if not self.creating and not attrs:
            raise serializers.ValidationError("Provide a field to change.")
        return attrs
