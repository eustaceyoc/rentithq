"""Resident API serializers. The workspace comes from the membership."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rest_framework import serializers

from common.api.scope import reject_client_scope
from organizations.models import Workspace
from residents.models import Resident


def _workspace(context: Mapping[str, Any]) -> Workspace:
    workspace = context.get("workspace")
    if not isinstance(workspace, Workspace):
        raise serializers.ValidationError("The active workspace is missing.")
    return workspace


class ResidentSerializer(serializers.ModelSerializer[Resident]):
    workspace_id = serializers.UUIDField(read_only=True)
    user_id = serializers.UUIDField(read_only=True, allow_null=True)
    account_email = serializers.SerializerMethodField()

    class Meta:
        model = Resident
        fields = (
            "id",
            "workspace_id",
            "user_id",
            "account_email",
            "first_name",
            "last_name",
            "email",
            "phone",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_account_email(self, obj: Resident) -> str:
        if obj.user_id is None or obj.user is None:
            return ""
        return obj.user.email


class ResidentWriteSerializer(serializers.Serializer[dict[str, Any]]):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    email = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    account_email = serializers.CharField(required=False, allow_blank=True)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.creating = bool(kwargs.pop("creating", False))
        super().__init__(*args, **kwargs)
        if self.creating:
            self.fields["first_name"].required = True
            self.fields["last_name"].required = True

    def validate_first_name(self, value: str) -> str:
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Enter a first name.")
        return name

    def validate_last_name(self, value: str) -> str:
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Enter a last name.")
        return name

    def validate_phone(self, value: str) -> str:
        return value.strip()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        reject_client_scope(
            self.initial_data,
            _workspace(self.context),
            creating=self.creating,
        )
        if not self.creating and not attrs:
            raise serializers.ValidationError("Provide a field to change.")
        return attrs
