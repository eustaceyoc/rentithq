"""Property endpoints. Scope comes from the caller's active membership."""

from __future__ import annotations

import uuid
from typing import Any

from rest_framework import serializers, status
from rest_framework.exceptions import NotAuthenticated, NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from common.api.pagination import StandardPagination
from organizations.access import (
    WORKSPACE_HEADER,
    parse_uuid,
    resolve_active_membership,
)
from organizations.models import Membership
from properties.permissions import (
    ensure_can_manage_properties,
    ensure_can_view_properties,
)
from properties.serializers import (
    BedSerializer,
    BedWriteSerializer,
    BuildingSerializer,
    BuildingWriteSerializer,
    FloorSerializer,
    FloorWriteSerializer,
    PropertySerializer,
    PropertyWriteSerializer,
    SpaceSerializer,
    SpaceWriteSerializer,
)
from properties.services import (
    create_bed,
    create_building,
    create_floor,
    create_property,
    create_space,
    delete_bed,
    delete_building,
    delete_floor,
    delete_property,
    delete_space,
    get_bed,
    get_building,
    get_floor,
    get_property,
    get_space,
    list_beds,
    list_buildings,
    list_floors,
    list_properties,
    list_spaces,
    update_bed,
    update_building,
    update_floor,
    update_property,
    update_space,
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


def _filter_id(request: Request, key: str) -> uuid.UUID | None:
    """A parent filter outside the active workspace is a 404, not an empty page.

    The lookup itself happens in the service. A malformed id is already a 404.
    Query-string workspace ids are ignored by not reading them.
    """
    raw = request.query_params.get(key)
    if raw is None or not raw.strip():
        return None
    parsed = parse_uuid(raw)
    if parsed is None:
        raise NotFound()
    return parsed


def _context(actor: Membership) -> dict[str, Any]:
    return {"workspace": actor.workspace}


class PropertyListCreateView(APIView):
    def get(self, request: Request) -> Response:
        actor = _actor(request)
        ensure_can_view_properties(actor)
        return _paginated(self, request, list_properties(actor), PropertySerializer)

    def post(self, request: Request) -> Response:
        actor = _actor(request)
        ensure_can_manage_properties(actor)
        serializer = PropertyWriteSerializer(
            data=request.data,
            require_name=True,
            context=_context(actor),
        )
        serializer.is_valid(raise_exception=True)
        row = create_property(actor=actor, data=serializer.validated_data)
        return Response(PropertySerializer(row).data, status=status.HTTP_201_CREATED)


class PropertyDetailView(APIView):
    def get(self, request: Request, property_id: str) -> Response:
        actor = _actor(request)
        ensure_can_view_properties(actor)
        return Response(PropertySerializer(get_property(actor, property_id)).data)

    def patch(self, request: Request, property_id: str) -> Response:
        actor = _actor(request)
        ensure_can_manage_properties(actor)
        serializer = PropertyWriteSerializer(
            data=request.data,
            context=_context(actor),
        )
        serializer.is_valid(raise_exception=True)
        row = update_property(
            actor=actor,
            raw_id=property_id,
            data=serializer.validated_data,
        )
        return Response(PropertySerializer(row).data)

    def delete(self, request: Request, property_id: str) -> Response:
        actor = _actor(request)
        ensure_can_manage_properties(actor)
        delete_property(actor=actor, raw_id=property_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BuildingListCreateView(APIView):
    def get(self, request: Request) -> Response:
        actor = _actor(request)
        ensure_can_view_properties(actor)
        return _paginated(
            self,
            request,
            list_buildings(actor, property_id=_filter_id(request, "property_id")),
            BuildingSerializer,
        )

    def post(self, request: Request) -> Response:
        actor = _actor(request)
        ensure_can_manage_properties(actor)
        serializer = BuildingWriteSerializer(
            data=request.data,
            creating=True,
            context=_context(actor),
        )
        serializer.is_valid(raise_exception=True)
        row = create_building(actor=actor, data=serializer.validated_data)
        return Response(BuildingSerializer(row).data, status=status.HTTP_201_CREATED)


class BuildingDetailView(APIView):
    def get(self, request: Request, building_id: str) -> Response:
        actor = _actor(request)
        ensure_can_view_properties(actor)
        return Response(BuildingSerializer(get_building(actor, building_id)).data)

    def patch(self, request: Request, building_id: str) -> Response:
        actor = _actor(request)
        ensure_can_manage_properties(actor)
        serializer = BuildingWriteSerializer(
            data=request.data,
            context=_context(actor),
        )
        serializer.is_valid(raise_exception=True)
        row = update_building(
            actor=actor,
            raw_id=building_id,
            data=serializer.validated_data,
        )
        return Response(BuildingSerializer(row).data)

    def delete(self, request: Request, building_id: str) -> Response:
        actor = _actor(request)
        ensure_can_manage_properties(actor)
        delete_building(actor=actor, raw_id=building_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FloorListCreateView(APIView):
    def get(self, request: Request) -> Response:
        actor = _actor(request)
        ensure_can_view_properties(actor)
        return _paginated(
            self,
            request,
            list_floors(
                actor,
                property_id=_filter_id(request, "property_id"),
                building_id=_filter_id(request, "building_id"),
            ),
            FloorSerializer,
        )

    def post(self, request: Request) -> Response:
        actor = _actor(request)
        ensure_can_manage_properties(actor)
        serializer = FloorWriteSerializer(
            data=request.data,
            creating=True,
            context=_context(actor),
        )
        serializer.is_valid(raise_exception=True)
        row = create_floor(actor=actor, data=serializer.validated_data)
        return Response(FloorSerializer(row).data, status=status.HTTP_201_CREATED)


class FloorDetailView(APIView):
    def get(self, request: Request, floor_id: str) -> Response:
        actor = _actor(request)
        ensure_can_view_properties(actor)
        return Response(FloorSerializer(get_floor(actor, floor_id)).data)

    def patch(self, request: Request, floor_id: str) -> Response:
        actor = _actor(request)
        ensure_can_manage_properties(actor)
        serializer = FloorWriteSerializer(
            data=request.data,
            context=_context(actor),
        )
        serializer.is_valid(raise_exception=True)
        row = update_floor(
            actor=actor,
            raw_id=floor_id,
            data=serializer.validated_data,
        )
        return Response(FloorSerializer(row).data)

    def delete(self, request: Request, floor_id: str) -> Response:
        actor = _actor(request)
        ensure_can_manage_properties(actor)
        delete_floor(actor=actor, raw_id=floor_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SpaceListCreateView(APIView):
    def get(self, request: Request) -> Response:
        actor = _actor(request)
        ensure_can_view_properties(actor)
        return _paginated(
            self,
            request,
            list_spaces(
                actor,
                property_id=_filter_id(request, "property_id"),
                building_id=_filter_id(request, "building_id"),
                floor_id=_filter_id(request, "floor_id"),
            ),
            SpaceSerializer,
        )

    def post(self, request: Request) -> Response:
        actor = _actor(request)
        ensure_can_manage_properties(actor)
        serializer = SpaceWriteSerializer(
            data=request.data,
            creating=True,
            context=_context(actor),
        )
        serializer.is_valid(raise_exception=True)
        row = create_space(actor=actor, data=serializer.validated_data)
        return Response(SpaceSerializer(row).data, status=status.HTTP_201_CREATED)


class SpaceDetailView(APIView):
    def get(self, request: Request, space_id: str) -> Response:
        actor = _actor(request)
        ensure_can_view_properties(actor)
        return Response(SpaceSerializer(get_space(actor, space_id)).data)

    def patch(self, request: Request, space_id: str) -> Response:
        actor = _actor(request)
        ensure_can_manage_properties(actor)
        serializer = SpaceWriteSerializer(
            data=request.data,
            context=_context(actor),
        )
        serializer.is_valid(raise_exception=True)
        row = update_space(
            actor=actor,
            raw_id=space_id,
            data=serializer.validated_data,
        )
        return Response(SpaceSerializer(row).data)

    def delete(self, request: Request, space_id: str) -> Response:
        actor = _actor(request)
        ensure_can_manage_properties(actor)
        delete_space(actor=actor, raw_id=space_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BedListCreateView(APIView):
    def get(self, request: Request) -> Response:
        actor = _actor(request)
        ensure_can_view_properties(actor)
        return _paginated(
            self,
            request,
            list_beds(actor, space_id=_filter_id(request, "space_id")),
            BedSerializer,
        )

    def post(self, request: Request) -> Response:
        actor = _actor(request)
        ensure_can_manage_properties(actor)
        serializer = BedWriteSerializer(
            data=request.data,
            creating=True,
            context=_context(actor),
        )
        serializer.is_valid(raise_exception=True)
        row = create_bed(actor=actor, data=serializer.validated_data)
        return Response(BedSerializer(row).data, status=status.HTTP_201_CREATED)


class BedDetailView(APIView):
    def get(self, request: Request, bed_id: str) -> Response:
        actor = _actor(request)
        ensure_can_view_properties(actor)
        return Response(BedSerializer(get_bed(actor, bed_id)).data)

    def patch(self, request: Request, bed_id: str) -> Response:
        actor = _actor(request)
        ensure_can_manage_properties(actor)
        serializer = BedWriteSerializer(
            data=request.data,
            context=_context(actor),
        )
        serializer.is_valid(raise_exception=True)
        row = update_bed(
            actor=actor,
            raw_id=bed_id,
            data=serializer.validated_data,
        )
        return Response(BedSerializer(row).data)

    def delete(self, request: Request, bed_id: str) -> Response:
        actor = _actor(request)
        ensure_can_manage_properties(actor)
        delete_bed(actor=actor, raw_id=bed_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
