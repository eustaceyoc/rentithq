"""Tenancy, assignment, and availability endpoints."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers, status
from rest_framework.exceptions import NotAuthenticated, NotFound, ValidationError
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
from residents.models import Resident
from tenancies.serializers import (
    AssignmentSerializer,
    AssignmentWriteSerializer,
    CheckOutSerializer,
    EndTenancySerializer,
    TenancySerializer,
    TenancyWriteSerializer,
    TransferSerializer,
)
from tenancies.services import (
    cancel_assignment,
    cancel_tenancy,
    check_in_assignment,
    check_out_assignment,
    create_assignment,
    create_tenancy,
    end_tenancy,
    get_assignment,
    get_tenancy,
    list_assignments,
    list_availability,
    list_tenancies,
    transfer_assignment,
    update_assignment,
    update_tenancy,
)


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


def _on_date(request: Request) -> Any:
    raw = request.query_params.get("on")
    if raw is None or not raw.strip():
        raise ValidationError({"on": "Choose a date."})
    parsed = serializers.DateField().to_internal_value(raw)
    return parsed


class TenancyListCreateView(APIView):
    def get(self, request: Request) -> Response:
        return _paginated(
            self, request, list_tenancies(_actor(request)), TenancySerializer
        )

    def post(self, request: Request) -> Response:
        actor = _actor(request)
        serializer = TenancyWriteSerializer(
            data=request.data,
            creating=True,
            context={"workspace": actor.workspace},
        )
        serializer.is_valid(raise_exception=True)
        row = create_tenancy(actor=actor, data=serializer.validated_data)
        return Response(TenancySerializer(row).data, status=status.HTTP_201_CREATED)


class TenancyDetailView(APIView):
    def get(self, request: Request, tenancy_id: str) -> Response:
        return Response(
            TenancySerializer(get_tenancy(_actor(request), tenancy_id)).data
        )

    def patch(self, request: Request, tenancy_id: str) -> Response:
        actor = _actor(request)
        serializer = TenancyWriteSerializer(
            data=request.data,
            context={"workspace": actor.workspace},
        )
        serializer.is_valid(raise_exception=True)
        row = update_tenancy(
            actor=actor,
            raw_id=tenancy_id,
            data=serializer.validated_data,
        )
        return Response(TenancySerializer(row).data)


class TenancyEndView(APIView):
    def post(self, request: Request, tenancy_id: str) -> Response:
        actor = _actor(request)
        serializer = EndTenancySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = end_tenancy(
            actor=actor,
            raw_id=tenancy_id,
            ended_on=serializer.validated_data["ended_on"],
        )
        return Response(TenancySerializer(row).data)


class TenancyCancelView(APIView):
    def post(self, request: Request, tenancy_id: str) -> Response:
        return Response(
            TenancySerializer(
                cancel_tenancy(actor=_actor(request), raw_id=tenancy_id)
            ).data
        )


class AssignmentListCreateView(APIView):
    def get(self, request: Request) -> Response:
        return _paginated(
            self,
            request,
            list_assignments(_actor(request)),
            AssignmentSerializer,
        )

    def post(self, request: Request) -> Response:
        actor = _actor(request)
        serializer = AssignmentWriteSerializer(
            data=request.data,
            creating=True,
            context={"workspace": actor.workspace},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        resident = Resident.objects.filter(
            workspace_id=actor.workspace_id,
            id=data["resident_id"],
        ).first()
        if resident is None:
            raise NotFound()
        tenancy = None
        if data.get("tenancy_id") is not None:
            from tenancies.models import Tenancy

            tenancy = Tenancy.objects.filter(
                workspace_id=actor.workspace_id,
                id=data["tenancy_id"],
            ).first()
            if tenancy is None:
                raise NotFound()
        row = create_assignment(
            actor=actor,
            resident=resident,
            space_id=data["space_id"],
            bed_id=data.get("bed_id"),
            start=data["start_date"],
            end=data.get("end_date"),
            tenancy=tenancy,
        )
        return Response(AssignmentSerializer(row).data, status=status.HTTP_201_CREATED)


class AssignmentDetailView(APIView):
    def get(self, request: Request, assignment_id: str) -> Response:
        return Response(
            AssignmentSerializer(get_assignment(_actor(request), assignment_id)).data
        )

    def patch(self, request: Request, assignment_id: str) -> Response:
        actor = _actor(request)
        serializer = AssignmentWriteSerializer(
            data=request.data,
            context={"workspace": actor.workspace},
        )
        serializer.is_valid(raise_exception=True)
        row = update_assignment(
            actor=actor,
            raw_id=assignment_id,
            data=serializer.validated_data,
        )
        return Response(AssignmentSerializer(row).data)


class AssignmentCheckInView(APIView):
    def post(self, request: Request, assignment_id: str) -> Response:
        return Response(
            AssignmentSerializer(
                check_in_assignment(actor=_actor(request), raw_id=assignment_id)
            ).data
        )


class AssignmentCheckOutView(APIView):
    def post(self, request: Request, assignment_id: str) -> Response:
        actor = _actor(request)
        serializer = CheckOutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = check_out_assignment(
            actor=actor,
            raw_id=assignment_id,
            end=serializer.validated_data["end_date"],
        )
        return Response(AssignmentSerializer(row).data)


class AssignmentCancelView(APIView):
    def post(self, request: Request, assignment_id: str) -> Response:
        return Response(
            AssignmentSerializer(
                cancel_assignment(actor=_actor(request), raw_id=assignment_id)
            ).data
        )


class AssignmentTransferView(APIView):
    def post(self, request: Request, assignment_id: str) -> Response:
        actor = _actor(request)
        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        row = transfer_assignment(
            actor=actor,
            raw_id=assignment_id,
            space_id=data["space_id"],
            bed_id=data.get("bed_id"),
            move_on=data["start_date"],
        )
        return Response(AssignmentSerializer(row).data, status=status.HTTP_201_CREATED)


class AvailabilityView(APIView):
    def get(self, request: Request) -> Response:
        actor = _actor(request)
        raw_property = request.query_params.get("property_id")
        property_id = None
        if raw_property is not None and raw_property.strip():
            property_id = parse_uuid(raw_property)
            if property_id is None:
                raise NotFound()
        rows = list_availability(
            actor,
            on=_on_date(request),
            property_id=property_id,
        )
        paginator: PageNumberPagination = StandardPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        selected = rows if page is None else page
        return paginator.get_paginated_response(selected)
