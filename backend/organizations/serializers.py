"""API serializers. Clients cannot assign a workspace they do not belong to."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import User
from organizations.models import Membership, Workspace
from organizations.validation import currency_code_or_error, timezone_name_or_error


class WorkspaceSerializer(serializers.ModelSerializer[Workspace]):
    class Meta:
        model = Workspace
        fields = (
            "id",
            "name",
            "currency_code",
            "timezone",
            "status",
            "plan_code",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class WorkspaceWriteSerializer(serializers.Serializer[dict[str, str]]):
    name = serializers.CharField(max_length=200, required=False)
    currency_code = serializers.CharField(max_length=3, required=False)
    timezone = serializers.CharField(max_length=64, required=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.require_name = bool(kwargs.pop("require_name", False))
        super().__init__(*args, **kwargs)
        if self.require_name:
            self.fields["name"].required = True
            self.fields["currency_code"].required = True

    def validate_name(self, value: str) -> str:
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Enter a workspace name.")
        return name

    def validate_currency_code(self, value: str) -> str:
        try:
            return currency_code_or_error(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate_timezone(self, value: str) -> str:
        try:
            return timezone_name_or_error(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate(self, attrs: dict[str, str]) -> dict[str, str]:
        initial = self.initial_data
        if isinstance(initial, dict) and "status" in initial:
            raise serializers.ValidationError(
                {"status": ("Workspace status is changed in platform administration.")}
            )
        if isinstance(initial, dict) and ("plan_code" in initial or "plan" in initial):
            raise serializers.ValidationError(
                {
                    "plan_code": (
                        "The account plan is changed in platform administration."
                    )
                }
            )
        if self.require_name and "timezone" not in attrs:
            attrs["timezone"] = "UTC"
        if not self.require_name and not attrs:
            raise serializers.ValidationError("Provide a field to change.")
        return attrs


class MemberUserSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name")


class MembershipSerializer(serializers.ModelSerializer[Membership]):
    user = MemberUserSerializer(read_only=True)
    workspace_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Membership
        fields = ("id", "role", "is_active", "workspace_id", "user", "created_at")
        read_only_fields = fields


class SessionWorkspaceSerializer(serializers.ModelSerializer[Workspace]):
    class Meta:
        model = Workspace
        fields = ("id", "name", "currency_code", "timezone", "status", "plan_code")


class SessionMembershipSerializer(serializers.ModelSerializer[Membership]):
    workspace = SessionWorkspaceSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ("id", "role", "workspace")


class SessionUserSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name")


def session_payload(user: User) -> dict[str, Any]:
    memberships = (
        Membership.objects.select_related("workspace")
        .filter(user=user, is_active=True)
        .order_by("workspace__name", "id")
    )
    return {
        "user": SessionUserSerializer(user).data,
        "memberships": SessionMembershipSerializer(memberships, many=True).data,
    }


_MEMBERSHIP_FROZEN = (
    "id",
    "workspace",
    "workspace_id",
    "user",
    "user_id",
    "email",
    "is_active",
    "is_staff",
    "is_superuser",
)


class MembershipCreateSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Membership.Role.choices)
    workspace_id = serializers.UUIDField(required=False)

    def validate_email(self, value: str) -> str:
        try:
            return User.objects.normalize_user_email(value)
        except ValueError as exc:
            raise serializers.ValidationError("Enter a valid email address.") from exc

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        workspace = self.context.get("workspace")
        if not isinstance(workspace, Workspace):
            raise serializers.ValidationError("The active workspace is missing.")
        requested = attrs.get("workspace_id")
        if requested is not None and requested != workspace.id:
            raise serializers.ValidationError(
                {
                    "workspace_id": (
                        "A membership can only be created in the active workspace."
                    )
                }
            )
        initial = self.initial_data
        if isinstance(initial, dict):
            if "id" in initial:
                raise serializers.ValidationError(
                    {"id": "A membership id cannot be chosen by the client."}
                )
            if "is_staff" in initial or "is_superuser" in initial:
                raise serializers.ValidationError(
                    {"is_staff": "Membership cannot change platform access."}
                )
        return attrs


class MembershipUpdateSerializer(serializers.Serializer[dict[str, str]]):
    role = serializers.ChoiceField(choices=Membership.Role.choices)

    def validate(self, attrs: dict[str, str]) -> dict[str, str]:
        initial = self.initial_data
        if isinstance(initial, dict):
            for key in _MEMBERSHIP_FROZEN:
                if key in initial:
                    raise serializers.ValidationError(
                        {key: "This field cannot be changed."}
                    )
        return attrs
