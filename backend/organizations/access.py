"""Resolve the active workspace from memberships. The header only selects."""

from __future__ import annotations

import uuid

from django.db.models import QuerySet
from rest_framework.exceptions import APIException, NotFound

from accounts.models import User
from organizations.models import Membership, Workspace

WORKSPACE_HEADER = "X-Workspace-Id"


class WorkspaceRequired(APIException):
    status_code = 400
    default_detail = "Choose a workspace."
    default_code = "workspace_required"
    api_code = "workspace_required"
    api_message = "Choose a workspace."


class WorkspaceUnavailable(APIException):
    status_code = 403
    default_detail = "This workspace is not available."
    default_code = "workspace_unavailable"
    api_code = "workspace_unavailable"
    api_message = "This workspace is not available."


def _active_memberships(user: User) -> QuerySet[Membership]:
    return Membership.objects.select_related("workspace").filter(
        user=user,
        is_active=True,
    )


def parse_uuid(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return uuid.UUID(text)
    except ValueError:
        return None


def resolve_active_membership(user: User, workspace_header: str | None) -> Membership:
    """Return the caller's membership for this request, or raise a generic error.

    A header that is not one of the user's active memberships is a 404. It does
    not reveal whether that workspace exists. Several memberships and no header
    is 400 workspace_required. One membership may omit the header.
    """
    if not user.is_active:
        raise NotFound()

    header = (workspace_header or "").strip()
    memberships = _active_memberships(user)
    if header:
        workspace_id = parse_uuid(header)
        if workspace_id is None:
            raise NotFound()
        membership = memberships.filter(workspace_id=workspace_id).first()
        if membership is None:
            raise NotFound()
    else:
        chosen = list(memberships.order_by("created_at", "id")[:2])
        if not chosen:
            raise NotFound()
        if len(chosen) > 1:
            raise WorkspaceRequired()
        membership = chosen[0]

    if membership.workspace.status != Workspace.Status.ACTIVE:
        raise WorkspaceUnavailable()
    return membership


def workspaces_for_user(user: User) -> QuerySet[Workspace]:
    if not user.is_active:
        return Workspace.objects.none()
    return Workspace.objects.filter(
        memberships__user=user,
        memberships__is_active=True,
    ).distinct()


def membership_for_workspace(user: User, raw_workspace_id: str) -> Membership:
    """Membership implied by a workspace URL. Missing access is a generic 404."""
    if not user.is_active:
        raise NotFound()
    workspace_id = parse_uuid(raw_workspace_id)
    if workspace_id is None:
        raise NotFound()
    membership = _active_memberships(user).filter(workspace_id=workspace_id).first()
    if membership is None:
        raise NotFound()
    return membership


def ensure_workspace_is_active(workspace: Workspace) -> None:
    if workspace.status != Workspace.Status.ACTIVE:
        raise WorkspaceUnavailable()


def visible_memberships(actor: Membership) -> QuerySet[Membership]:
    queryset = Membership.objects.select_related("user").filter(
        workspace_id=actor.workspace_id,
        is_active=True,
    )
    if actor.role == Membership.Role.RESIDENT:
        queryset = queryset.filter(user_id=actor.user_id)
    return queryset


def membership_in_scope(actor: Membership, raw_membership_id: str) -> Membership:
    membership_id = parse_uuid(raw_membership_id)
    if membership_id is None:
        raise NotFound()
    membership = visible_memberships(actor).filter(id=membership_id).first()
    if membership is None:
        raise NotFound()
    return membership
