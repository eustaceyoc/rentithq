"""Tenancy and assignment changes. Overlap is decided here and in the database."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from rest_framework.exceptions import NotFound, ValidationError

from bookings.models import Booking
from organizations.access import parse_uuid
from organizations.models import Membership
from properties.models import Bed, Property, Space
from residents.models import Resident
from residents.permissions import (
    ensure_can_read_occupancy,
    ensure_can_write_occupancy,
    ensure_staff_read,
)
from tenancies.inventory import (
    assert_available,
    bed_has_history,
    day_before,
    expands,
    hold_for_new_bed,
    lock_spaces,
    raise_if_overlap_constraint,
    release_bed_blocks,
    replace_blocks,
)
from tenancies.models import Assignment, Tenancy

BLOCKING = (Assignment.Status.CONFIRMED, Assignment.Status.ACTIVE)


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


def _save(instance: Tenancy | Assignment) -> None:
    try:
        instance.save()
    except DjangoValidationError as exc:
        raise _as_drf(exc) from exc
    except IntegrityError as exc:
        raise_if_overlap_constraint(exc)
        raise


def _dates(start: date, end: date | None) -> None:
    if end is not None and end < start:
        raise ValidationError(
            {
                "end_date": (
                    "The end date is the last occupied day and "
                    "cannot be before the start date."
                )
            }
        )


def _visible_residents(actor: Membership) -> QuerySet[Resident]:
    rows = Resident.objects.filter(workspace_id=actor.workspace_id)
    if actor.role == Membership.Role.RESIDENT:
        rows = rows.filter(user_id=actor.user_id)
    return rows


def _resident(actor: Membership, raw: str | uuid.UUID) -> Resident:
    row = _visible_residents(actor).filter(id=_parse_id(raw)).first()
    if row is None:
        raise NotFound()
    return row


def _space(workspace_id: uuid.UUID, raw: str | uuid.UUID) -> Space:
    row = Space.objects.filter(workspace_id=workspace_id, id=_parse_id(raw)).first()
    if row is None:
        raise NotFound()
    return row


def _target(
    workspace_id: uuid.UUID,
    space_id: str | uuid.UUID,
    bed_id: str | uuid.UUID | None,
) -> tuple[Space, Bed | None]:
    space = _space(workspace_id, space_id)
    if bed_id is None:
        return space, None
    bed = Bed.objects.filter(workspace_id=workspace_id, id=_parse_id(bed_id)).first()
    if bed is None:
        raise NotFound()
    if space.kind != Space.Kind.ROOM:
        raise ValidationError({"bed_id": "A whole unit does not have beds."})
    if bed.space_id != space.id:
        raise ValidationError({"bed_id": "Choose a bed in this room."})
    return space, bed


def _scoped_assignments(actor: Membership) -> QuerySet[Assignment]:
    ensure_can_read_occupancy(actor)
    rows = Assignment.objects.select_related(
        "resident",
        "space",
        "bed",
    ).filter(workspace_id=actor.workspace_id)
    if actor.role == Membership.Role.RESIDENT:
        rows = rows.filter(resident__user_id=actor.user_id)
    return rows


def _assignment(actor: Membership, raw_id: str) -> Assignment:
    row = _scoped_assignments(actor).filter(id=_parse_id(raw_id)).first()
    if row is None:
        raise NotFound()
    return row


def _lock_assignment(actor: Membership, raw_id: str) -> Assignment:
    # Lock the stay row only. Nullable relations are outer joins, and
    # PostgreSQL refuses FOR UPDATE on the nullable side of an outer join.
    row = (
        Assignment.objects.select_for_update()
        .filter(workspace_id=actor.workspace_id, id=_parse_id(raw_id))
        .first()
    )
    if row is None:
        raise NotFound()
    if actor.role == Membership.Role.RESIDENT and row.resident.user_id != actor.user_id:
        raise NotFound()
    return row


def list_tenancies(actor: Membership) -> QuerySet[Tenancy]:
    ensure_can_read_occupancy(actor)
    rows = Tenancy.objects.select_related("resident").filter(
        workspace_id=actor.workspace_id
    )
    if actor.role == Membership.Role.RESIDENT:
        rows = rows.filter(resident__user_id=actor.user_id)
    return rows


def get_tenancy(actor: Membership, raw_id: str) -> Tenancy:
    row = list_tenancies(actor).filter(id=_parse_id(raw_id)).first()
    if row is None:
        raise NotFound()
    return row


def list_assignments(actor: Membership) -> QuerySet[Assignment]:
    return _scoped_assignments(actor)


def get_assignment(actor: Membership, raw_id: str) -> Assignment:
    return _assignment(actor, raw_id)


@transaction.atomic
def create_assignment(
    *,
    actor: Membership,
    resident: Resident,
    space_id: str | uuid.UUID,
    bed_id: str | uuid.UUID | None,
    start: date,
    end: date | None,
    booking: Booking | None = None,
    tenancy: Tenancy | None = None,
    status: str = Assignment.Status.CONFIRMED,
) -> Assignment:
    """Insert one blocking stay. Caller must already be allowed to write."""
    ensure_can_write_occupancy(actor)
    if resident.workspace_id != actor.workspace_id:
        raise NotFound()
    _dates(start, end)
    space, bed = _target(actor.workspace_id, space_id, bed_id)
    if tenancy is not None:
        if tenancy.workspace_id != actor.workspace_id:
            raise NotFound()
        if tenancy.resident_id != resident.id:
            raise ValidationError(
                {"resident_id": "Choose the resident on this agreement."}
            )
        if tenancy.status != Tenancy.Status.ACTIVE:
            raise ValidationError({"tenancy_id": "This agreement is not active."})
    if booking is not None and booking.workspace_id != actor.workspace_id:
        raise NotFound()
    lock_spaces([space.id])
    space.refresh_from_db()
    if bed is not None:
        bed.refresh_from_db()
    assert_available(
        workspace_id=actor.workspace_id,
        space=space,
        bed=bed,
        start=start,
        end=end,
        check_maintenance=True,
    )
    row = Assignment(
        workspace=actor.workspace,
        resident=resident,
        space=space,
        bed=bed,
        booking=booking,
        tenancy=tenancy,
        status=status,
        start_date=start,
        end_date=end,
    )
    _save(row)
    replace_blocks(row)
    return row


@transaction.atomic
def create_tenancy(*, actor: Membership, data: dict[str, Any]) -> Tenancy:
    ensure_can_write_occupancy(actor)
    resident = _resident(actor, data["resident_id"])
    start = data["start_date"]
    end = data.get("end_date")
    _dates(start, end)
    row = Tenancy(
        workspace=actor.workspace,
        resident=resident,
        status=Tenancy.Status.ACTIVE,
        start_date=start,
        end_date=end,
        fee_amount=data["fee_amount"],
        fee_period=data["fee_period"],
        deposit_amount=data.get("deposit_amount", 0),
        currency_code=actor.workspace.currency_code,
    )
    _save(row)
    if "space_id" in data and data["space_id"] is not None:
        status = (
            Assignment.Status.ACTIVE
            if data.get("check_in")
            else Assignment.Status.CONFIRMED
        )
        create_assignment(
            actor=actor,
            resident=resident,
            space_id=data["space_id"],
            bed_id=data.get("bed_id"),
            start=start,
            end=end,
            tenancy=row,
            status=status,
        )
    return row


@transaction.atomic
def update_tenancy(
    *,
    actor: Membership,
    raw_id: str,
    data: dict[str, Any],
) -> Tenancy:
    ensure_can_write_occupancy(actor)
    row = (
        Tenancy.objects.select_for_update()
        .filter(workspace_id=actor.workspace_id, id=_parse_id(raw_id))
        .first()
    )
    if row is None:
        raise NotFound()
    if row.status != Tenancy.Status.ACTIVE:
        raise ValidationError({"detail": "This agreement can no longer be changed."})
    if "fee_amount" in data:
        row.fee_amount = data["fee_amount"]
    if "fee_period" in data:
        row.fee_period = data["fee_period"]
    if "deposit_amount" in data:
        row.deposit_amount = data["deposit_amount"]
    if "end_date" in data:
        _dates(row.start_date, data["end_date"])
        row.end_date = data["end_date"]
    _save(row)
    return row


def _blocking_for_tenancy(tenancy: Tenancy) -> QuerySet[Assignment]:
    return Assignment.objects.filter(tenancy=tenancy, status__in=BLOCKING)


@transaction.atomic
def end_tenancy(*, actor: Membership, raw_id: str, ended_on: date) -> Tenancy:
    ensure_can_write_occupancy(actor)
    row = (
        Tenancy.objects.select_for_update()
        .filter(workspace_id=actor.workspace_id, id=_parse_id(raw_id))
        .first()
    )
    if row is None:
        raise NotFound()
    if row.status != Tenancy.Status.ACTIVE:
        raise ValidationError({"detail": "This agreement is not active."})
    if ended_on < row.start_date:
        raise ValidationError(
            {"ended_on": "The agreement cannot end before it starts."}
        )
    if _blocking_for_tenancy(row).exists():
        raise ValidationError(
            {"detail": "Check out the stay before ending the agreement."}
        )
    row.status = Tenancy.Status.ENDED
    row.ended_on = ended_on
    _save(row)
    return row


@transaction.atomic
def cancel_tenancy(*, actor: Membership, raw_id: str) -> Tenancy:
    ensure_can_write_occupancy(actor)
    row = (
        Tenancy.objects.select_for_update()
        .select_related("resident")
        .filter(workspace_id=actor.workspace_id, id=_parse_id(raw_id))
        .first()
    )
    if row is None:
        raise NotFound()
    if row.status != Tenancy.Status.ACTIVE:
        raise ValidationError({"detail": "This agreement is not active."})
    stays = list(Assignment.objects.filter(tenancy=row))
    if any(stay.status == Assignment.Status.ACTIVE for stay in stays):
        raise ValidationError(
            {"detail": "Check out the stay before cancelling the agreement."}
        )
    if any(
        stay.status in (Assignment.Status.CHECKED_OUT, Assignment.Status.TRANSFERRED)
        for stay in stays
    ):
        raise ValidationError(
            {
                "detail": (
                    "This agreement already has occupancy history. "
                    "End it instead of cancelling it."
                )
            }
        )
    for stay in stays:
        if stay.status == Assignment.Status.CONFIRMED:
            cancel_assignment(actor=actor, raw_id=str(stay.id))
    row.status = Tenancy.Status.CANCELLED
    _save(row)
    return row


@transaction.atomic
def update_assignment(
    *,
    actor: Membership,
    raw_id: str,
    data: dict[str, Any],
) -> Assignment:
    ensure_can_write_occupancy(actor)
    row = _lock_assignment(actor, raw_id)
    if row.status not in BLOCKING:
        raise ValidationError({"detail": "This stay is already finished."})
    lock_spaces([row.space_id])
    start = data.get("start_date", row.start_date)
    end = data.get("end_date", row.end_date)
    _dates(start, end)
    growing = expands(row.start_date, row.end_date, start, end)
    row.space.refresh_from_db()
    if row.bed_id is not None and row.bed is not None:
        row.bed.refresh_from_db()
    assert_available(
        workspace_id=actor.workspace_id,
        space=row.space,
        bed=row.bed,
        start=start,
        end=end,
        exclude_id=row.id,
        check_maintenance=growing,
    )
    row.start_date = start
    row.end_date = end
    _save(row)
    replace_blocks(row)
    return row


@transaction.atomic
def check_in_assignment(*, actor: Membership, raw_id: str) -> Assignment:
    ensure_can_write_occupancy(actor)
    row = _lock_assignment(actor, raw_id)
    if row.status != Assignment.Status.CONFIRMED:
        raise ValidationError({"detail": "Only a confirmed stay can be checked in."})
    lock_spaces([row.space_id])
    row.space.refresh_from_db()
    if row.bed is not None:
        row.bed.refresh_from_db()
    assert_available(
        workspace_id=actor.workspace_id,
        space=row.space,
        bed=row.bed,
        start=row.start_date,
        end=row.end_date,
        exclude_id=row.id,
        check_maintenance=True,
    )
    row.status = Assignment.Status.ACTIVE
    _save(row)
    replace_blocks(row)
    return row


@transaction.atomic
def check_out_assignment(
    *,
    actor: Membership,
    raw_id: str,
    end: date,
) -> Assignment:
    ensure_can_write_occupancy(actor)
    row = _lock_assignment(actor, raw_id)
    if row.status != Assignment.Status.ACTIVE:
        raise ValidationError({"detail": "Only an active stay can be checked out."})
    if end < row.start_date:
        raise ValidationError(
            {"end_date": "The last occupied day cannot be before the start date."}
        )
    if row.end_date is not None and end > row.end_date:
        raise ValidationError(
            {
                "end_date": (
                    "The last occupied day cannot be after the planned end. "
                    "Update the stay first."
                )
            }
        )
    lock_spaces([row.space_id])
    row.end_date = end
    row.status = Assignment.Status.CHECKED_OUT
    _save(row)
    replace_blocks(row)
    return row


@transaction.atomic
def cancel_assignment(*, actor: Membership, raw_id: str) -> Assignment:
    ensure_can_write_occupancy(actor)
    row = _lock_assignment(actor, raw_id)
    if row.status == Assignment.Status.ACTIVE:
        raise ValidationError(
            {
                "detail": (
                    "Check out an active stay. "
                    "Cancellation is for a reservation that has not started."
                )
            }
        )
    if row.status != Assignment.Status.CONFIRMED:
        raise ValidationError({"detail": "This stay is already finished."})
    lock_spaces([row.space_id])
    row.status = Assignment.Status.CANCELLED
    _save(row)
    replace_blocks(row)
    booking = row.booking
    if booking is not None and booking.status == Booking.Status.CONFIRMED:
        still_open = Assignment.objects.filter(
            booking_id=booking.id,
            status__in=BLOCKING,
        ).exists()
        if not still_open:
            booking.status = Booking.Status.CANCELLED
            booking.save()
    return row


@transaction.atomic
def transfer_assignment(
    *,
    actor: Membership,
    raw_id: str,
    space_id: str | uuid.UUID,
    bed_id: str | uuid.UUID | None,
    move_on: date,
) -> Assignment:
    """Close the old stay the day before `move_on` and append a new stay."""
    ensure_can_write_occupancy(actor)
    row = _lock_assignment(actor, raw_id)
    if row.status not in BLOCKING:
        raise ValidationError({"detail": "This stay is already finished."})
    if move_on <= row.start_date:
        raise ValidationError(
            {"start_date": "The move day has to be after the stay starts."}
        )
    if row.end_date is not None and move_on > row.end_date:
        raise ValidationError({"start_date": "Choose a move day during this stay."})
    space, bed = _target(actor.workspace_id, space_id, bed_id)
    if space.id == row.space_id and (bed.id if bed else None) == row.bed_id:
        raise ValidationError({"space_id": "Choose a different space or bed."})
    original_end = row.end_date
    original_status = row.status
    lock_spaces([row.space_id, space.id])
    space.refresh_from_db()
    if bed is not None:
        bed.refresh_from_db()
    previous_end = day_before(move_on)
    row.end_date = previous_end
    row.status = Assignment.Status.TRANSFERRED
    _save(row)
    replace_blocks(row)
    assert_available(
        workspace_id=actor.workspace_id,
        space=space,
        bed=bed,
        start=move_on,
        end=original_end,
        check_maintenance=True,
    )
    moved = Assignment(
        workspace=actor.workspace,
        resident=row.resident,
        space=space,
        bed=bed,
        booking=row.booking,
        tenancy=row.tenancy,
        transferred_from=row,
        status=original_status,
        start_date=move_on,
        end_date=original_end,
    )
    _save(moved)
    replace_blocks(moved)
    return moved


def list_availability(
    actor: Membership,
    *,
    on: date,
    property_id: uuid.UUID | None,
) -> list[dict[str, Any]]:
    ensure_staff_read(actor)
    spaces = Space.objects.select_related("property").filter(
        workspace_id=actor.workspace_id
    )
    if property_id is not None:
        if not Property.objects.filter(
            workspace_id=actor.workspace_id,
            id=property_id,
        ).exists():
            raise NotFound()
        spaces = spaces.filter(property_id=property_id)
    space_rows = list(spaces.order_by("property__name", "name", "id"))
    space_ids = [space.id for space in space_rows]
    beds = list(Bed.objects.filter(space_id__in=space_ids).order_by("name", "id"))
    stays = list(
        Assignment.objects.select_related("resident")
        .filter(
            workspace_id=actor.workspace_id,
            status__in=BLOCKING,
            space_id__in=space_ids,
            start_date__lte=on,
        )
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=on))
    )
    beds_by_space: dict[uuid.UUID, list[Bed]] = {}
    for bed in beds:
        beds_by_space.setdefault(bed.space_id, []).append(bed)
    results: list[dict[str, Any]] = []
    for space in space_rows:
        whole = next(
            (
                stay
                for stay in stays
                if stay.space_id == space.id and stay.bed_id is None
            ),
            None,
        )
        room_beds = beds_by_space.get(space.id, [])
        bed_stays = [
            stay
            for stay in stays
            if stay.space_id == space.id and stay.bed_id is not None
        ]
        results.append(
            _availability_row(
                space=space,
                whole=whole,
                bed_stays=bed_stays,
                on=on,
            )
        )
        for bed in room_beds:
            own = next((stay for stay in bed_stays if stay.bed_id == bed.id), None)
            results.append(
                _bed_availability_row(space=space, bed=bed, own=own, whole=whole, on=on)
            )
    return results


def _state_for_target(availability: str, block_reason: str, occupied: bool) -> str:
    if occupied:
        return "occupied"
    if availability != Space.Availability.ACTIVE:
        return "unavailable"
    if block_reason:
        return "unavailable"
    return "free"


def _availability_row(
    *,
    space: Space,
    whole: Assignment | None,
    bed_stays: list[Assignment],
    on: date,
) -> dict[str, Any]:
    partly = whole is None and bool(bed_stays) and space.kind == Space.Kind.ROOM
    occupied = whole is not None
    state = _state_for_target(space.availability, space.block_reason, occupied)
    if partly and state == "free":
        state = "partly_occupied"
    stay = whole
    return {
        "on": on.isoformat(),
        "property_id": str(space.property_id),
        "property_name": space.property.name,
        "space_id": str(space.id),
        "space_name": space.name,
        "space_kind": space.kind,
        "bed_id": None,
        "bed_name": None,
        "state": state,
        "assignment_id": None if stay is None else str(stay.id),
        "resident_name": None if stay is None else stay.resident.display_name,
    }


def _bed_availability_row(
    *,
    space: Space,
    bed: Bed,
    own: Assignment | None,
    whole: Assignment | None,
    on: date,
) -> dict[str, Any]:
    stay = own or whole
    occupied = stay is not None
    if bed.availability != Space.Availability.ACTIVE:
        state = _state_for_target(bed.availability, bed.block_reason, occupied)
    else:
        state = _state_for_target(space.availability, space.block_reason, occupied)
    return {
        "on": on.isoformat(),
        "property_id": str(space.property_id),
        "property_name": space.property.name,
        "space_id": str(space.id),
        "space_name": space.name,
        "space_kind": space.kind,
        "bed_id": str(bed.id),
        "bed_name": bed.name,
        "state": state,
        "assignment_id": None if stay is None else str(stay.id),
        "resident_name": None if stay is None else stay.resident.display_name,
    }


def sync_bed_created(bed: Bed) -> None:
    hold_for_new_bed(bed)


def sync_bed_moved(bed: Bed) -> None:
    if bed_has_history(bed):
        raise ValidationError(
            {
                "space_id": (
                    "This bed has occupancy history and cannot move to another room."
                )
            }
        )
    release_bed_blocks(bed)
    hold_for_new_bed(bed)
