"""Workspace reports. Totals use the same money and date rules as the records."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from billing.balances import ZERO, invoice_outstanding
from billing.models import Payment, Refund
from billing.services import list_arrears
from common.money import money_to_api_string
from maintenance.services import visible_request_rows
from organizations.models import Membership
from properties.models import Property
from reports.permissions import (
    ensure_maintenance_report,
    ensure_money_report,
    ensure_occupancy_report,
)
from tenancies.models import Assignment, Tenancy
from tenancies.services import list_availability

UPCOMING_LIMIT = 100
_STATUSES = (
    "open",
    "assigned",
    "in_progress",
    "completed",
    "cancelled",
)
_PRIORITIES = ("low", "normal", "high", "urgent")
_SPACE_STATES = ("occupied", "partly_occupied", "free", "unavailable")
_BED_STATES = ("occupied", "free", "unavailable")


def _counts(keys: tuple[str, ...]) -> dict[str, int]:
    return {key: 0 for key in keys}


def occupancy_report(
    actor: Membership,
    *,
    on: date,
    within_days: int,
) -> dict[str, Any]:
    ensure_occupancy_report(actor)
    if within_days < 1 or within_days > 366:
        raise ValidationError({"within_days": "Choose between 1 and 366 days."})
    board = list_availability(actor, on=on, property_id=None)
    spaces = {
        "unit": _counts(_SPACE_STATES),
        "room": _counts(_SPACE_STATES),
    }
    beds = _counts(_BED_STATES)
    properties: dict[str, dict[str, Any]] = {
        str(prop.id): {
            "property_id": str(prop.id),
            "property_name": prop.name,
            "occupied": 0,
            "partly_occupied": 0,
            "free": 0,
            "unavailable": 0,
        }
        for prop in Property.objects.filter(workspace_id=actor.workspace_id).order_by(
            "name",
            "id",
        )
    }
    for row in board:
        if row["bed_id"] is None:
            kind = str(row["space_kind"])
            state = str(row["state"])
            if kind in spaces and state in spaces[kind]:
                spaces[kind][state] += 1
            bucket = properties[str(row["property_id"])]
            if state in bucket:
                bucket[state] += 1
        else:
            state = str(row["state"])
            if state in beds:
                beds[state] += 1
    window_end = on + timedelta(days=within_days)
    tenancies = list(
        Tenancy.objects.select_related("resident")
        .filter(
            workspace_id=actor.workspace_id,
            status=Tenancy.Status.ACTIVE,
            end_date__gte=on,
            end_date__lte=window_end,
        )
        .order_by("end_date", "id")
    )
    bookings = list(
        Assignment.objects.select_related("resident", "space")
        .filter(
            workspace_id=actor.workspace_id,
            status__in=(Assignment.Status.CONFIRMED, Assignment.Status.ACTIVE),
            tenancy__isnull=True,
            end_date__gte=on,
            end_date__lte=window_end,
        )
        .order_by("end_date", "id")
    )
    upcoming: list[dict[str, Any]] = []
    for tenancy in tenancies:
        if tenancy.end_date is None:
            continue
        upcoming.append(
            {
                "kind": "tenancy",
                "resident_name": tenancy.resident.display_name,
                "label": "Agreement",
                "end_date": tenancy.end_date.isoformat(),
            }
        )
    for stay in bookings:
        if stay.end_date is None:
            continue
        upcoming.append(
            {
                "kind": "booking",
                "resident_name": stay.resident.display_name,
                "label": stay.space.name,
                "end_date": stay.end_date.isoformat(),
            }
        )
    upcoming.sort(key=lambda item: (str(item["end_date"]), str(item["resident_name"])))
    active_residents = (
        Tenancy.objects.filter(
            workspace_id=actor.workspace_id,
            status=Tenancy.Status.ACTIVE,
        )
        .values("resident_id")
        .distinct()
        .count()
    )
    return {
        "on": on.isoformat(),
        "within_days": within_days,
        "spaces": spaces,
        "beds": beds,
        "properties": list(properties.values()),
        "active_tenancies": Tenancy.objects.filter(
            workspace_id=actor.workspace_id,
            status=Tenancy.Status.ACTIVE,
        ).count(),
        "active_residents": active_residents,
        "upcoming_count": len(upcoming),
        "upcoming_truncated": len(upcoming) > UPCOMING_LIMIT,
        "upcoming_move_outs": upcoming[:UPCOMING_LIMIT],
    }


def arrears_report(actor: Membership, *, on: date) -> dict[str, Any]:
    ensure_money_report(actor)
    rows = list_arrears(actor, on)
    by_resident: dict[str, dict[str, Any]] = {}
    total = ZERO
    for invoice in rows:
        outstanding = invoice_outstanding(invoice)
        total += outstanding
        bucket = by_resident.setdefault(
            str(invoice.resident_id),
            {
                "resident_id": str(invoice.resident_id),
                "resident_name": invoice.resident.display_name,
                "invoice_count": 0,
                "outstanding_amount": ZERO,
            },
        )
        bucket["invoice_count"] += 1
        bucket["outstanding_amount"] += outstanding
    residents = []
    for bucket in by_resident.values():
        amount = bucket["outstanding_amount"]
        assert isinstance(amount, Decimal)
        residents.append(
            {
                "resident_id": bucket["resident_id"],
                "resident_name": bucket["resident_name"],
                "invoice_count": bucket["invoice_count"],
                "outstanding_amount": money_to_api_string(amount),
            }
        )
    residents.sort(key=lambda item: str(item["resident_name"]))
    return {
        "on": on.isoformat(),
        "currency_code": actor.workspace.currency_code,
        "invoice_count": len(rows),
        "outstanding_amount": money_to_api_string(total),
        "residents": residents,
    }


def collections_report(actor: Membership, *, start: date, end: date) -> dict[str, Any]:
    ensure_money_report(actor)
    if end < start:
        raise ValidationError({"to": "The end date is before the start date."})
    if (end - start).days > 366:
        raise ValidationError({"to": "Choose a range of 366 days or fewer."})
    payments = Payment.objects.filter(
        workspace_id=actor.workspace_id,
        status=Payment.Status.RECORDED,
        paid_on__gte=start,
        paid_on__lte=end,
    )
    collected = payments.aggregate(total=Sum("amount"))["total"] or ZERO
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "amount": ZERO}
    )
    for payment in payments.order_by("method", "reference"):
        bucket = grouped[payment.method]
        bucket["count"] += 1
        bucket["amount"] += payment.amount
    refunds = Refund.objects.filter(
        payment__workspace_id=actor.workspace_id,
        payment__status=Payment.Status.RECORDED,
        refunded_on__gte=start,
        refunded_on__lte=end,
    )
    refunded = refunds.aggregate(total=Sum("amount"))["total"] or ZERO
    by_method = [
        {
            "method": method,
            "count": grouped[method]["count"],
            "amount": money_to_api_string(grouped[method]["amount"]),
        }
        for method in sorted(grouped)
    ]
    net = (collected - refunded).quantize(Decimal("0.0001"))
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "currency_code": actor.workspace.currency_code,
        "payment_count": payments.count(),
        "collected_amount": money_to_api_string(collected),
        "refund_count": refunds.count(),
        "refunded_amount": money_to_api_string(refunded),
        "net_amount": money_to_api_string(net),
        "by_method": by_method,
    }


def maintenance_report(actor: Membership) -> dict[str, Any]:
    """Counts follow the requests this caller is allowed to see.

    A maintenance login does not receive the workspace total. An owner,
    property manager, or finance login does.
    """
    ensure_maintenance_report(actor)
    rows = visible_request_rows(actor)
    counts = _counts(_STATUSES)
    priorities = _counts(_PRIORITIES)
    for status, priority in rows.values_list("status", "priority"):
        if status in counts:
            counts[status] += 1
        if status in {"open", "assigned", "in_progress"} and priority in priorities:
            priorities[priority] += 1
    scope = "assigned" if actor.role == Membership.Role.MAINTENANCE else "workspace"
    open_count = counts["open"] + counts["assigned"] + counts["in_progress"]
    return {
        "scope": scope,
        "counts": counts,
        "open_count": open_count,
        "by_priority": priorities,
    }


def occupancy_csv(report: dict[str, Any]) -> list[list[object]]:
    rows: list[list[object]] = [
        ["property_name", "occupied", "partly_occupied", "free", "unavailable"]
    ]
    properties = report["properties"]
    assert isinstance(properties, list)
    for item in properties:
        assert isinstance(item, dict)
        rows.append(
            [
                item["property_name"],
                item["occupied"],
                item["partly_occupied"],
                item["free"],
                item["unavailable"],
            ]
        )
    return rows


def arrears_csv(report: dict[str, Any]) -> list[list[object]]:
    rows: list[list[object]] = [
        ["resident_name", "invoice_count", "outstanding_amount", "currency_code"]
    ]
    residents = report["residents"]
    assert isinstance(residents, list)
    for item in residents:
        assert isinstance(item, dict)
        rows.append(
            [
                item["resident_name"],
                item["invoice_count"],
                item["outstanding_amount"],
                report["currency_code"],
            ]
        )
    return rows


def collections_csv(report: dict[str, Any]) -> list[list[object]]:
    rows: list[list[object]] = [["method", "count", "amount", "currency_code"]]
    methods = report["by_method"]
    assert isinstance(methods, list)
    for item in methods:
        assert isinstance(item, dict)
        rows.append(
            [
                item["method"],
                item["count"],
                item["amount"],
                report["currency_code"],
            ]
        )
    rows.append(
        [
            "total",
            report["payment_count"],
            report["collected_amount"],
            report["currency_code"],
        ]
    )
    return rows


def maintenance_csv(report: dict[str, Any]) -> list[list[object]]:
    rows: list[list[object]] = [["status", "count"]]
    counts = report["counts"]
    assert isinstance(counts, dict)
    for status in _STATUSES:
        rows.append([status, counts[status]])
    return rows
