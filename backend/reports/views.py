"""Report endpoints. CSV uses the same scope as the JSON body."""

from __future__ import annotations

from datetime import date
from typing import Any

from django.http import HttpResponse
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from organizations.access import WORKSPACE_HEADER, resolve_active_membership
from organizations.models import Membership
from reports.csv_export import csv_response
from reports.services import (
    arrears_csv,
    arrears_report,
    collections_csv,
    collections_report,
    maintenance_csv,
    maintenance_report,
    occupancy_csv,
    occupancy_report,
)


def _actor(request: Request) -> Membership:
    user = request.user
    if not isinstance(user, User) or not user.is_active:
        raise NotAuthenticated()
    return resolve_active_membership(user, request.headers.get(WORKSPACE_HEADER))


def _date(request: Request, key: str) -> date:
    raw = request.query_params.get(key)
    if raw is None or not raw.strip():
        raise ValidationError({key: "Choose a date."})
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationError({key: "Choose a date."}) from exc


def _within_days(request: Request) -> int:
    raw = request.query_params.get("within_days", "30")
    if raw is None or not str(raw).strip():
        return 30
    try:
        return int(str(raw))
    except ValueError as exc:
        raise ValidationError(
            {"within_days": "Choose between 1 and 366 days."}
        ) from exc


def _wants_csv(request: Request) -> bool:
    export = request.query_params.get("export")
    if export is None or export == "":
        return False
    if export == "csv":
        return True
    raise ValidationError({"export": "Choose csv or omit the export."})


def _send(
    request: Request, filename: str, payload: dict[str, Any], rows: list[list[object]]
) -> HttpResponse | Response:
    if _wants_csv(request):
        return csv_response(filename, rows)
    return Response(payload)


class OccupancyReportView(APIView):
    def get(self, request: Request) -> HttpResponse | Response:
        actor = _actor(request)
        payload = occupancy_report(
            actor,
            on=_date(request, "on"),
            within_days=_within_days(request),
        )
        return _send(request, "occupancy.csv", payload, occupancy_csv(payload))


class ArrearsReportView(APIView):
    def get(self, request: Request) -> HttpResponse | Response:
        actor = _actor(request)
        payload = arrears_report(actor, on=_date(request, "on"))
        return _send(request, "arrears.csv", payload, arrears_csv(payload))


class CollectionsReportView(APIView):
    def get(self, request: Request) -> HttpResponse | Response:
        actor = _actor(request)
        payload = collections_report(
            actor,
            start=_date(request, "from"),
            end=_date(request, "to"),
        )
        return _send(request, "collections.csv", payload, collections_csv(payload))


class MaintenanceReportView(APIView):
    def get(self, request: Request) -> HttpResponse | Response:
        actor = _actor(request)
        payload = maintenance_report(actor)
        return _send(request, "maintenance.csv", payload, maintenance_csv(payload))
