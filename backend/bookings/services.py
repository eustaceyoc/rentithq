"""Reservations. Converting one creates a tenancy and keeps the stay."""

from __future__ import annotations

import uuid
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import QuerySet
from rest_framework.exceptions import NotFound, ValidationError

from bookings.models import Booking
from organizations.access import parse_uuid
from organizations.models import Membership
from residents.models import Resident
from residents.permissions import ensure_can_read_occupancy, ensure_can_write_occupancy
from tenancies.models import Assignment, Tenancy
from tenancies.services import (
    cancel_assignment,
    check_in_assignment,
    create_assignment,
    update_assignment,
)


def _as_drf(exc: DjangoValidationError) -> ValidationError:
    if hasattr(exc, "error_dict"):
        details: dict[str, Any] = {}
        for key, errors in exc.error_dict.items():
            messages: list[str] = []
            for error in errors:
                messages.extend(error.messages)
            details[str(key)] = messages[0] if len(messages) == 1 else messages
        return ValidationError(details)
    return ValidationError(exc.messages)


def _parse_id(raw: str | uuid.UUID) -> uuid.UUID:
    if isinstance(raw, uuid.UUID):
        return raw
    parsed = parse_uuid(raw)
    if parsed is None:
        raise NotFound()
    return parsed


def _visible(actor: Membership) -> QuerySet[Booking]:
    ensure_can_read_occupancy(actor)
    rows = Booking.objects.select_related("resident").filter(
        workspace_id=actor.workspace_id
    )
    if actor.role == Membership.Role.RESIDENT:
        rows = rows.filter(resident__user_id=actor.user_id)
    return rows


def list_bookings(actor: Membership) -> QuerySet[Booking]:
    return _visible(actor)


def get_booking(actor: Membership, raw_id: str) -> Booking:
    row = _visible(actor).filter(id=_parse_id(raw_id)).first()
    if row is None:
        raise NotFound()
    return row


def _resident(actor: Membership, raw: str | uuid.UUID) -> Resident:
    rows = Resident.objects.filter(workspace_id=actor.workspace_id, id=_parse_id(raw))
    row = rows.first()
    if row is None:
        raise NotFound()
    return row


def _open_assignment(booking: Booking) -> Assignment:
    row = (
        Assignment.objects.select_related("space", "bed")
        .filter(
            booking=booking,
            status__in=(Assignment.Status.CONFIRMED, Assignment.Status.ACTIVE),
        )
        .order_by("-start_date", "id")
        .first()
    )
    if row is None:
        raise ValidationError({"detail": "This reservation has no open stay."})
    return row


@transaction.atomic
def create_booking(*, actor: Membership, data: dict[str, Any]) -> Booking:
    ensure_can_write_occupancy(actor)
    resident = _resident(actor, data["resident_id"])
    booking = Booking(
        workspace=actor.workspace,
        resident=resident,
        status=Booking.Status.CONFIRMED,
        start_date=data["start_date"],
        end_date=data.get("end_date"),
    )
    try:
        booking.save()
    except DjangoValidationError as exc:
        raise _as_drf(exc) from exc
    create_assignment(
        actor=actor,
        resident=resident,
        space_id=data["space_id"],
        bed_id=data.get("bed_id"),
        start=booking.start_date,
        end=booking.end_date,
        booking=booking,
        status=Assignment.Status.CONFIRMED,
    )
    return booking


@transaction.atomic
def update_booking(
    *,
    actor: Membership,
    raw_id: str,
    data: dict[str, Any],
) -> Booking:
    ensure_can_write_occupancy(actor)
    booking = (
        Booking.objects.select_for_update()
        .filter(workspace_id=actor.workspace_id, id=_parse_id(raw_id))
        .first()
    )
    if booking is None:
        raise NotFound()
    if booking.status != Booking.Status.CONFIRMED:
        raise ValidationError({"detail": "This reservation can no longer be changed."})
    stay = _open_assignment(booking)
    if (
        stay.status != Assignment.Status.CONFIRMED
        or stay.transferred_from_id is not None
    ):
        raise ValidationError(
            {
                "detail": (
                    "Change dates on the stay after it has moved or been checked in."
                )
            }
        )
    start = data.get("start_date", booking.start_date)
    end = data.get("end_date", booking.end_date)
    update_assignment(
        actor=actor,
        raw_id=str(stay.id),
        data={"start_date": start, "end_date": end},
    )
    booking.start_date = start
    booking.end_date = end
    try:
        booking.save()
    except DjangoValidationError as exc:
        raise _as_drf(exc) from exc
    return booking


@transaction.atomic
def cancel_booking(*, actor: Membership, raw_id: str) -> Booking:
    ensure_can_write_occupancy(actor)
    booking = (
        Booking.objects.select_for_update()
        .filter(workspace_id=actor.workspace_id, id=_parse_id(raw_id))
        .first()
    )
    if booking is None:
        raise NotFound()
    if booking.status != Booking.Status.CONFIRMED:
        raise ValidationError(
            {"detail": "This reservation can no longer be cancelled."}
        )
    stays = list(Assignment.objects.filter(booking=booking))
    if any(stay.status == Assignment.Status.ACTIVE for stay in stays):
        raise ValidationError(
            {"detail": "Check out the stay before cancelling the reservation."}
        )
    for stay in stays:
        if stay.status == Assignment.Status.CONFIRMED:
            cancel_assignment(actor=actor, raw_id=str(stay.id))
    booking.refresh_from_db()
    if booking.status != Booking.Status.CANCELLED:
        booking.status = Booking.Status.CANCELLED
        booking.save()
    return booking


@transaction.atomic
def convert_booking(*, actor: Membership, raw_id: str, data: dict[str, Any]) -> Tenancy:
    ensure_can_write_occupancy(actor)
    booking = (
        Booking.objects.select_for_update()
        .select_related("resident")
        .filter(workspace_id=actor.workspace_id, id=_parse_id(raw_id))
        .first()
    )
    if booking is None:
        raise NotFound()
    if booking.status != Booking.Status.CONFIRMED:
        raise ValidationError(
            {"detail": "Only a confirmed reservation can be converted."}
        )
    stay = _open_assignment(booking)
    tenancy = Tenancy(
        workspace=actor.workspace,
        resident=booking.resident,
        booking=booking,
        status=Tenancy.Status.ACTIVE,
        start_date=booking.start_date,
        end_date=booking.end_date,
        fee_amount=data["fee_amount"],
        fee_period=data["fee_period"],
        deposit_amount=data.get("deposit_amount", 0),
        currency_code=actor.workspace.currency_code,
    )
    try:
        tenancy.save()
    except DjangoValidationError as exc:
        raise _as_drf(exc) from exc
    stay.tenancy = tenancy
    try:
        stay.save()
    except DjangoValidationError as exc:
        raise _as_drf(exc) from exc
    booking.status = Booking.Status.CONVERTED
    booking.save()
    if data.get("check_in") and stay.status == Assignment.Status.CONFIRMED:
        check_in_assignment(actor=actor, raw_id=str(stay.id))
    return tenancy
