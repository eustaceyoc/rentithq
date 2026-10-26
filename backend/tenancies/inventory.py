"""Inclusive stays, locks, and the holds that back the exclusion constraints."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from django.db import IntegrityError
from django.db.backends.postgresql.psycopg_any import DateRange
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from properties.models import Bed, Space
from tenancies.models import Assignment, OccupancyBlock

BLOCKING = (Assignment.Status.CONFIRMED, Assignment.Status.ACTIVE)
OVERLAP_MESSAGE = "Those dates overlap another stay."


def stay_period(start: date, end: date | None) -> DateRange:
    """Inclusive range. A null end stays open. The next day is free."""
    if end is None:
        return DateRange(start, None, "[)")
    return DateRange(start, end, "[]")


def dates_overlap(
    start_a: date,
    end_a: date | None,
    start_b: date,
    end_b: date | None,
) -> bool:
    """True when new_start <= existing_end and new_end >= existing_start.

    A null end is open-ended and compares as later than every date.
    """
    started_before_existing_end = end_b is None or start_a <= end_b
    ends_after_existing_start = end_a is None or end_a >= start_b
    return started_before_existing_end and ends_after_existing_start


def overlap_error() -> ValidationError:
    return ValidationError({"end_date": OVERLAP_MESSAGE})


def raise_if_overlap_constraint(exc: IntegrityError) -> None:
    text = str(exc)
    if "block_bed_no_overlap" in text or "block_space_no_overlap" in text:
        raise overlap_error() from exc


def lock_spaces(space_ids: list[uuid.UUID]) -> None:
    """Lock rooms and their beds in id order so two writers cannot deadlock."""
    ordered = sorted(set(space_ids))
    if not ordered:
        return
    list(Space.objects.select_for_update().filter(id__in=ordered).order_by("id"))
    list(
        Bed.objects.select_for_update()
        .filter(space_id__in=ordered)
        .order_by("space_id", "id")
    )


def availability_error(space: Space, bed: Bed | None) -> str | None:
    """Refuse a new blocking stay on a space that is not active."""
    space_error = _target_error("space", space.availability, space.block_reason)
    if space_error is not None:
        return space_error
    if bed is not None:
        return _target_error("bed", bed.availability, bed.block_reason)
    if space.kind != Space.Kind.ROOM:
        return None
    for item in Bed.objects.filter(space_id=space.id).order_by("id"):
        if item.availability == Space.Availability.ACTIVE:
            continue
        if (
            item.availability == Space.Availability.UNAVAILABLE
            and item.block_reason == "maintenance"
        ):
            return "A bed in this room is unavailable for maintenance."
        return "A bed in this room is not available for a new stay."
    return None


def _target_error(kind: str, availability: str, block_reason: str) -> str | None:
    if availability == Space.Availability.ACTIVE:
        return None
    if availability == Space.Availability.UNAVAILABLE and block_reason == "maintenance":
        return f"This {kind} is unavailable for maintenance."
    return f"This {kind} is not available for a new stay."


def conflicting_assignments(
    *,
    workspace_id: uuid.UUID,
    space: Space,
    bed: Bed | None,
    start: date,
    end: date | None,
    exclude_id: uuid.UUID | None = None,
) -> Assignment | None:
    """Return one confirmed or active stay that overlaps this target."""
    rows = Assignment.objects.filter(
        workspace_id=workspace_id,
        status__in=BLOCKING,
    )
    if exclude_id is not None:
        rows = rows.exclude(id=exclude_id)
    rows = rows.filter(Q(end_date__isnull=True) | Q(end_date__gte=start))
    if end is not None:
        rows = rows.filter(start_date__lte=end)
    if bed is not None:
        rows = rows.filter(Q(bed_id=bed.id) | Q(space_id=space.id, bed__isnull=True))
    else:
        rows = rows.filter(space_id=space.id)
    return rows.order_by("start_date", "id").first()


def expands(
    old_start: date,
    old_end: date | None,
    new_start: date,
    new_end: date | None,
) -> bool:
    if new_start < old_start:
        return True
    if old_end is None:
        return False
    if new_end is None:
        return True
    return new_end > old_end


def replace_blocks(assignment: Assignment) -> None:
    """Rebuild derived holds. Historical assignments keep no hold rows."""
    OccupancyBlock.objects.filter(assignment_id=assignment.id).delete()
    if assignment.status not in BLOCKING:
        return
    period = stay_period(assignment.start_date, assignment.end_date)
    rows = [
        OccupancyBlock(
            assignment=assignment,
            workspace_id=assignment.workspace_id,
            space_id=assignment.space_id,
            bed_id=assignment.bed_id,
            period=period,
        )
    ]
    if assignment.bed_id is None and assignment.space.kind == Space.Kind.ROOM:
        bed_ids = Bed.objects.filter(space_id=assignment.space_id).order_by("id")
        rows.extend(
            OccupancyBlock(
                assignment=assignment,
                workspace_id=assignment.workspace_id,
                space_id=assignment.space_id,
                bed_id=bed.id,
                period=period,
            )
            for bed in bed_ids
        )
    try:
        OccupancyBlock.objects.bulk_create(rows)
    except IntegrityError as exc:
        raise_if_overlap_constraint(exc)
        raise


def assert_available(
    *,
    workspace_id: uuid.UUID,
    space: Space,
    bed: Bed | None,
    start: date,
    end: date | None,
    exclude_id: uuid.UUID | None = None,
    check_maintenance: bool,
) -> None:
    if check_maintenance:
        message = availability_error(space, bed)
        if message is not None:
            field = "bed_id" if bed is not None else "space_id"
            raise ValidationError({field: message})
    conflict = conflicting_assignments(
        workspace_id=workspace_id,
        space=space,
        bed=bed,
        start=start,
        end=end,
        exclude_id=exclude_id,
    )
    if conflict is not None:
        raise overlap_error()


def day_before(value: date) -> date:
    return value - timedelta(days=1)


def bed_has_history(bed: Bed) -> bool:
    return Assignment.objects.filter(bed_id=bed.id).exists()


def release_bed_blocks(bed: Bed) -> None:
    """Drop derived holds when a bed with no stay history leaves a room."""
    OccupancyBlock.objects.filter(bed_id=bed.id).delete()


def hold_for_new_bed(bed: Bed) -> None:
    """A new bed inherits whole-room stays already covering that room."""
    stays = Assignment.objects.filter(
        space_id=bed.space_id,
        bed__isnull=True,
        status__in=BLOCKING,
    )
    rows = [
        OccupancyBlock(
            assignment=stay,
            workspace_id=stay.workspace_id,
            space_id=bed.space_id,
            bed_id=bed.id,
            period=stay_period(stay.start_date, stay.end_date),
        )
        for stay in stays
    ]
    if not rows:
        return
    try:
        OccupancyBlock.objects.bulk_create(rows)
    except IntegrityError as exc:
        raise_if_overlap_constraint(exc)
        raise
