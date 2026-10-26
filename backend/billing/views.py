"""Invoice, payment, allocation, and arrears endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any

from rest_framework import serializers, status
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from billing.models import Invoice
from billing.serializers import (
    AllocationSerializer,
    AllocationWriteSerializer,
    InvoiceSerializer,
    InvoiceWriteSerializer,
    PaymentSerializer,
    PaymentWriteSerializer,
    RefundSerializer,
    RefundWriteSerializer,
    ReversalSerializer,
    VoidSerializer,
)
from billing.services import (
    allocate_payment,
    get_invoice,
    get_payment,
    issue_invoice,
    list_arrears,
    list_invoices,
    list_payments,
    record_payment,
    record_refund,
    reverse_allocation,
    void_invoice,
    void_payment,
)
from common.api.pagination import StandardPagination
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


def _on_date(request: Request) -> date:
    raw = request.query_params.get("on")
    if raw is None or not raw.strip():
        raise ValidationError({"on": "Choose a date."})
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationError({"on": "Choose a date."}) from exc


class InvoiceListCreateView(APIView):
    def get(self, request: Request) -> Response:
        return _paginated(
            self,
            request,
            list_invoices(_actor(request)),
            InvoiceSerializer,
        )

    def post(self, request: Request) -> Response:
        actor = _actor(request)
        serializer = InvoiceWriteSerializer(
            data=request.data,
            context={"workspace": actor.workspace},
        )
        serializer.is_valid(raise_exception=True)
        row = issue_invoice(actor=actor, data=serializer.validated_data)
        return Response(InvoiceSerializer(row).data, status=status.HTTP_201_CREATED)


class InvoiceDetailView(APIView):
    def get(self, request: Request, invoice_id: str) -> Response:
        row = get_invoice(_actor(request), invoice_id)
        return Response(InvoiceSerializer(row).data)


class InvoiceVoidView(APIView):
    def post(self, request: Request, invoice_id: str) -> Response:
        actor = _actor(request)
        serializer = VoidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = void_invoice(
            actor=actor,
            raw_id=invoice_id,
            reason=serializer.validated_data["reason"],
            voided_on=serializer.validated_data["voided_on"],
        )
        return Response(InvoiceSerializer(row).data)


class PaymentListCreateView(APIView):
    def get(self, request: Request) -> Response:
        return _paginated(
            self, request, list_payments(_actor(request)), PaymentSerializer
        )

    def post(self, request: Request) -> Response:
        actor = _actor(request)
        serializer = PaymentWriteSerializer(
            data=request.data,
            context={"workspace": actor.workspace},
        )
        serializer.is_valid(raise_exception=True)
        row = record_payment(actor=actor, data=serializer.validated_data)
        return Response(PaymentSerializer(row).data, status=status.HTTP_201_CREATED)


class PaymentDetailView(APIView):
    """The payment detail is also the receipt."""

    def get(self, request: Request, payment_id: str) -> Response:
        row = get_payment(_actor(request), payment_id)
        return Response(PaymentSerializer(row).data)


class PaymentVoidView(APIView):
    def post(self, request: Request, payment_id: str) -> Response:
        actor = _actor(request)
        serializer = VoidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = void_payment(
            actor=actor,
            raw_id=payment_id,
            reason=serializer.validated_data["reason"],
            voided_on=serializer.validated_data["voided_on"],
        )
        return Response(PaymentSerializer(row).data)


class PaymentRefundView(APIView):
    def post(self, request: Request, payment_id: str) -> Response:
        actor = _actor(request)
        serializer = RefundWriteSerializer(
            data=request.data,
            context={"workspace": actor.workspace},
        )
        serializer.is_valid(raise_exception=True)
        row = record_refund(
            actor=actor,
            raw_payment_id=payment_id,
            data=serializer.validated_data,
        )
        return Response(RefundSerializer(row).data, status=status.HTTP_201_CREATED)


class AllocationCreateView(APIView):
    def post(self, request: Request) -> Response:
        actor = _actor(request)
        serializer = AllocationWriteSerializer(
            data=request.data,
            context={"workspace": actor.workspace},
        )
        serializer.is_valid(raise_exception=True)
        row = allocate_payment(actor=actor, data=serializer.validated_data)
        return Response(AllocationSerializer(row).data, status=status.HTTP_201_CREATED)


class AllocationReverseView(APIView):
    def post(self, request: Request, allocation_id: str) -> Response:
        actor = _actor(request)
        serializer = ReversalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = reverse_allocation(
            actor=actor,
            raw_id=allocation_id,
            reason=serializer.validated_data["reason"],
            reversed_on=serializer.validated_data["reversed_on"],
        )
        return Response(AllocationSerializer(row).data)


class ArrearsView(APIView):
    def get(self, request: Request) -> Response:
        actor = _actor(request)
        rows: list[Invoice] = list_arrears(actor, _on_date(request))
        return _paginated(self, request, rows, InvoiceSerializer)
