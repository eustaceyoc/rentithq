"""Booking endpoints."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers, status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from bookings.serializers import (
    BookingConvertSerializer,
    BookingSerializer,
    BookingWriteSerializer,
)
from bookings.services import (
    cancel_booking,
    convert_booking,
    create_booking,
    get_booking,
    list_bookings,
    update_booking,
)
from common.api.pagination import StandardPagination
from organizations.access import WORKSPACE_HEADER, resolve_active_membership
from organizations.models import Membership
from tenancies.serializers import TenancySerializer


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


class BookingListCreateView(APIView):
    def get(self, request: Request) -> Response:
        actor = _actor(request)
        return _paginated(self, request, list_bookings(actor), BookingSerializer)

    def post(self, request: Request) -> Response:
        actor = _actor(request)
        serializer = BookingWriteSerializer(
            data=request.data,
            creating=True,
            context={"workspace": actor.workspace},
        )
        serializer.is_valid(raise_exception=True)
        row = create_booking(actor=actor, data=serializer.validated_data)
        return Response(BookingSerializer(row).data, status=status.HTTP_201_CREATED)


class BookingDetailView(APIView):
    def get(self, request: Request, booking_id: str) -> Response:
        return Response(
            BookingSerializer(get_booking(_actor(request), booking_id)).data
        )

    def patch(self, request: Request, booking_id: str) -> Response:
        actor = _actor(request)
        serializer = BookingWriteSerializer(
            data=request.data,
            context={"workspace": actor.workspace},
        )
        serializer.is_valid(raise_exception=True)
        row = update_booking(
            actor=actor,
            raw_id=booking_id,
            data=serializer.validated_data,
        )
        return Response(BookingSerializer(row).data)


class BookingCancelView(APIView):
    def post(self, request: Request, booking_id: str) -> Response:
        return Response(
            BookingSerializer(
                cancel_booking(actor=_actor(request), raw_id=booking_id)
            ).data
        )


class BookingConvertView(APIView):
    def post(self, request: Request, booking_id: str) -> Response:
        actor = _actor(request)
        serializer = BookingConvertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenancy = convert_booking(
            actor=actor,
            raw_id=booking_id,
            data=serializer.validated_data,
        )
        return Response(TenancySerializer(tenancy).data, status=status.HTTP_201_CREATED)
