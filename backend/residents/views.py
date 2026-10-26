"""Resident endpoints. Scope comes from the caller's active membership."""

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
from organizations.access import WORKSPACE_HEADER, resolve_active_membership
from organizations.models import Membership
from residents.serializers import ResidentSerializer, ResidentWriteSerializer
from residents.services import (
    create_resident,
    delete_resident,
    get_resident,
    list_residents,
    update_resident,
)


def _user(request: Request) -> User:
    user = request.user
    if not isinstance(user, User) or not user.is_active:
        raise NotAuthenticated()
    return user


def _actor(request: Request) -> Membership:
    return resolve_active_membership(
        _user(request),
        request.headers.get(WORKSPACE_HEADER),
    )


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


class ResidentListCreateView(APIView):
    def get(self, request: Request) -> Response:
        actor = _actor(request)
        return _paginated(self, request, list_residents(actor), ResidentSerializer)

    def post(self, request: Request) -> Response:
        actor = _actor(request)
        serializer = ResidentWriteSerializer(
            data=request.data,
            creating=True,
            context={"workspace": actor.workspace},
        )
        serializer.is_valid(raise_exception=True)
        row = create_resident(actor=actor, data=serializer.validated_data)
        return Response(ResidentSerializer(row).data, status=status.HTTP_201_CREATED)


class ResidentDetailView(APIView):
    def get(self, request: Request, resident_id: str) -> Response:
        actor = _actor(request)
        return Response(ResidentSerializer(get_resident(actor, resident_id)).data)

    def patch(self, request: Request, resident_id: str) -> Response:
        actor = _actor(request)
        serializer = ResidentWriteSerializer(
            data=request.data,
            context={"workspace": actor.workspace},
        )
        serializer.is_valid(raise_exception=True)
        row = update_resident(
            actor=actor,
            raw_id=resident_id,
            data=serializer.validated_data,
        )
        return Response(ResidentSerializer(row).data)

    def delete(self, request: Request, resident_id: str) -> Response:
        actor = _actor(request)
        delete_resident(actor=actor, raw_id=resident_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
