"""Reject client control of identity and workspace on tenant writes."""

from __future__ import annotations

import uuid
from typing import Any

from rest_framework import serializers

from organizations.models import Workspace


def reject_client_scope(
    initial: Any,
    workspace: Workspace,
    *,
    creating: bool,
) -> None:
    """The active membership chooses the workspace. The client does not."""
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
            {"workspace_id": "A record can only be written in the active workspace."}
        )
