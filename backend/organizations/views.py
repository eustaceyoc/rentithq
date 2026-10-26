"""Workspace and membership endpoints. Scope is decided on the server."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers, status
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from common.api.pagination import StandardPagination
from organizations.access import (
    WORKSPACE_HEADER,
    ensure_workspace_is_active,
    membership_for_workspace,
    membership_in_scope,
    resolve_active_membership,
    visible_memberships,
    workspaces_for_user,
)
from organizations.models import Membership
from organizations.serializers import (
    MembershipCreateSerializer,
    MembershipSerializer,
    MembershipUpdateSerializer,
    WorkspaceSerializer,
    WorkspaceWriteSerializer,
)
from organizations.services import (
    add_member,
    change_member_role,
    create_workspace,
    deactivate_member,
    delete_workspace,
    update_workspace,
)


def require_user(request: Request) -> User:
    user = request.user
    if not isinstance(user, User) or not user.is_active:
        raise NotAuthenticated()
    return user


def paginated(
    view: APIView,
    request: Request,
    rows: Any,
    serializer: type[serializers.BaseSerializer[Any]],
) -> Response:
    paginator: PageNumberPagination = StandardPagination()
    page: list[Any] | None = paginator.paginate_queryset(rows, request, view=view)
    selected = list(rows) if page is None else page
    return paginator.get_paginated_response(serializer(selected, many=True).data)


class WorkspaceListCreateView(APIView):
    def get(self, request: Request) -> Response:
        user = require_user(request)
        return paginated(
            self,
            request,
            workspaces_for_user(user),
            WorkspaceSerializer,
        )

    def post(self, request: Request) -> Response:
        user = require_user(request)
        serializer = WorkspaceWriteSerializer(
            data=request.data,
            require_name=True,
        )
        serializer.is_valid(raise_exception=True)
        workspace = create_workspace(
            owner=user,
            name=serializer.validated_data["name"],
            currency_code=serializer.validated_data["currency_code"],
            timezone_name=serializer.validated_data.get("timezone", "UTC"),
        )
        return Response(
            WorkspaceSerializer(workspace).data,
            status=status.HTTP_201_CREATED,
        )


class WorkspaceDetailView(APIView):
    def get(self, request: Request, workspace_id: str) -> Response:
        user = require_user(request)
        membership = membership_for_workspace(user, workspace_id)
        return Response(WorkspaceSerializer(membership.workspace).data)

    def patch(self, request: Request, workspace_id: str) -> Response:
        user = require_user(request)
        membership = membership_for_workspace(user, workspace_id)
        ensure_workspace_is_active(membership.workspace)
        if membership.role != Membership.Role.OWNER:
            raise PermissionDenied()
        serializer = WorkspaceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workspace = update_workspace(
            actor=membership,
            workspace=membership.workspace,
            changes=serializer.validated_data,
        )
        return Response(WorkspaceSerializer(workspace).data)

    def delete(self, request: Request, workspace_id: str) -> Response:
        user = require_user(request)
        membership = membership_for_workspace(user, workspace_id)
        ensure_workspace_is_active(membership.workspace)
        if membership.role != Membership.Role.OWNER:
            raise PermissionDenied()
        delete_workspace(actor=membership, workspace=membership.workspace)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MembershipListCreateView(APIView):
    def get(self, request: Request) -> Response:
        user = require_user(request)
        actor = resolve_active_membership(user, request.headers.get(WORKSPACE_HEADER))
        return paginated(
            self,
            request,
            visible_memberships(actor),
            MembershipSerializer,
        )

    def post(self, request: Request) -> Response:
        user = require_user(request)
        actor = resolve_active_membership(user, request.headers.get(WORKSPACE_HEADER))
        if actor.role != Membership.Role.OWNER:
            raise PermissionDenied()
        serializer = MembershipCreateSerializer(
            data=request.data,
            context={"workspace": actor.workspace},
        )
        serializer.is_valid(raise_exception=True)
        membership = add_member(
            actor=actor,
            email=serializer.validated_data["email"],
            role=serializer.validated_data["role"],
        )
        return Response(
            MembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )


class MembershipDetailView(APIView):
    def get(self, request: Request, membership_id: str) -> Response:
        user = require_user(request)
        actor = resolve_active_membership(user, request.headers.get(WORKSPACE_HEADER))
        membership = membership_in_scope(actor, membership_id)
        return Response(MembershipSerializer(membership).data)

    def patch(self, request: Request, membership_id: str) -> Response:
        user = require_user(request)
        actor = resolve_active_membership(user, request.headers.get(WORKSPACE_HEADER))
        if actor.role != Membership.Role.OWNER:
            raise PermissionDenied()
        membership = membership_in_scope(actor, membership_id)
        serializer = MembershipUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = change_member_role(
            actor=actor,
            membership=membership,
            role=serializer.validated_data["role"],
        )
        return Response(MembershipSerializer(updated).data)

    def delete(self, request: Request, membership_id: str) -> Response:
        user = require_user(request)
        actor = resolve_active_membership(user, request.headers.get(WORKSPACE_HEADER))
        if actor.role != Membership.Role.OWNER:
            raise PermissionDenied()
        membership = membership_in_scope(actor, membership_id)
        deactivate_member(actor=actor, membership=membership)
        return Response(status=status.HTTP_204_NO_CONTENT)
