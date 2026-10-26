"""Maintenance request endpoints."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers, status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from common.api.pagination import StandardPagination
from maintenance.serializers import (
    MaintenanceCreateSerializer,
    MaintenanceRequestSerializer,
    MaintenanceUpdateWriteSerializer,
)
from maintenance.services import (
    create_request,
    get_request,
    list_requests,
    update_request,
)
from organizations.access import WORKSPACE_HEADER, resolve_active_membership
from organizations.models import Membership


def _actor(request: Request) -> Membership:
    user = request.user
    if not isinstance(user, User) or not user.is_active:
        raise NotAuthenticated()
    return resolve_active_membership(user, request.headers.get(WORKSPACE_HEADER))


def _paginated(
    view: APIView,
    request: Request,
    rows: Any,
    serializer: type[serializers.BaseSerializer[Any]],
) -> Response:
    paginator: PageNumberPagination = StandardPagination()
    page: list[Any] | None = paginator.paginate_queryset(rows, request, view=view)
    selected = list(rows) if page is None else page
    return paginator.get_paginated_response(serializer(selected, many=True).data)


class MaintenanceRequestListCreateView(APIView):
    def get(self, request: Request) -> Response:
        actor = _actor(request)
        rows = list_requests(
            actor,
            status=request.query_params.get("status"),
            priority=request.query_params.get("priority"),
        )
        return _paginated(self, request, rows, MaintenanceRequestSerializer)

    def post(self, request: Request) -> Response:
        actor = _actor(request)
        serializer = MaintenanceCreateSerializer(
            data=request.data,
            context={"workspace": actor.workspace},
        )
        serializer.is_valid(raise_exception=True)
        row = create_request(actor=actor, data=serializer.validated_data)
        return Response(
            MaintenanceRequestSerializer(row).data,
            status=status.HTTP_201_CREATED,
        )


class MaintenanceRequestDetailView(APIView):
    def get(self, request: Request, request_id: str) -> Response:
        row = get_request(_actor(request), request_id)
        return Response(MaintenanceRequestSerializer(row).data)

    def patch(self, request: Request, request_id: str) -> Response:
        actor = _actor(request)
        serializer = MaintenanceUpdateWriteSerializer(
            data=request.data,
            context={"workspace": actor.workspace},
        )
        serializer.is_valid(raise_exception=True)
        row = update_request(
            actor=actor,
            raw_id=request_id,
            data=serializer.validated_data,
        )
        return Response(MaintenanceRequestSerializer(row).data)
