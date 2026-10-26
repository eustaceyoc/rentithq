"""Property writes. The active membership decides the workspace."""

from __future__ import annotations

import uuid
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, QuerySet
from rest_framework.exceptions import NotFound, ValidationError

from organizations.access import parse_uuid
from organizations.models import Membership
from properties.models import Bed, Building, Floor, Property, Space
from properties.permissions import (
    ensure_can_manage_properties,
    ensure_can_view_properties,
)
from properties.validation import block_pair_error


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


def _discard(instance: Property | Building | Floor | Space | Bed) -> None:
    try:
        instance.delete()
    except ProtectedError as exc:
        raise ValidationError(
            {
                "detail": (
                    "This record still has occupancy history or a maintenance request. "
                    "The stay is kept and was not deleted."
                )
            }
        ) from exc


def _save(instance: Property | Building | Floor | Space | Bed) -> None:
    try:
        instance.save()
    except DjangoValidationError as exc:
        raise _as_drf(exc) from exc
    except IntegrityError as exc:
        raise ValidationError(
            {"name": "That name is already used in this place."}
        ) from exc


def _parse_id(raw: str | uuid.UUID) -> uuid.UUID:
    if isinstance(raw, uuid.UUID):
        return raw
    parsed = parse_uuid(raw)
    if parsed is None:
        raise NotFound()
    return parsed


def _require_block(availability: str, block_reason: str) -> None:
    error = block_pair_error(availability, block_reason)
    if error:
        raise ValidationError(error)


def _property(workspace_id: uuid.UUID, raw: str | uuid.UUID) -> Property:
    row = Property.objects.filter(
        workspace_id=workspace_id,
        id=_parse_id(raw),
    ).first()
    if row is None:
        raise NotFound()
    return row


def _building(workspace_id: uuid.UUID, raw: str | uuid.UUID) -> Building:
    row = Building.objects.filter(
        workspace_id=workspace_id,
        id=_parse_id(raw),
    ).first()
    if row is None:
        raise NotFound()
    return row


def _floor(workspace_id: uuid.UUID, raw: str | uuid.UUID) -> Floor:
    row = Floor.objects.filter(
        workspace_id=workspace_id,
        id=_parse_id(raw),
    ).first()
    if row is None:
        raise NotFound()
    return row


def _space(workspace_id: uuid.UUID, raw: str | uuid.UUID) -> Space:
    row = Space.objects.filter(
        workspace_id=workspace_id,
        id=_parse_id(raw),
    ).first()
    if row is None:
        raise NotFound()
    return row


def _building_on_property(
    workspace_id: uuid.UUID,
    property_id: uuid.UUID,
    raw: str | uuid.UUID | None,
) -> Building | None:
    if raw is None:
        return None
    building = _building(workspace_id, raw)
    if building.property_id != property_id:
        raise ValidationError({"building_id": "Choose a building on this property."})
    return building


def _floor_on_property(
    workspace_id: uuid.UUID,
    property_id: uuid.UUID,
    raw: str | uuid.UUID | None,
    building_id: uuid.UUID | None,
) -> Floor | None:
    if raw is None:
        return None
    floor = _floor(workspace_id, raw)
    if floor.property_id != property_id:
        raise ValidationError({"floor_id": "Choose a floor on this property."})
    if floor.building_id != building_id:
        raise ValidationError({"floor_id": "Choose a floor in the selected building."})
    return floor


def list_properties(actor: Membership) -> QuerySet[Property]:
    ensure_can_view_properties(actor)
    return Property.objects.filter(workspace_id=actor.workspace_id)


def get_property(actor: Membership, raw_id: str) -> Property:
    ensure_can_view_properties(actor)
    return _property(actor.workspace_id, raw_id)


@transaction.atomic
def create_property(*, actor: Membership, data: dict[str, Any]) -> Property:
    ensure_can_manage_properties(actor)
    row = Property(
        workspace=actor.workspace,
        name=data["name"],
        address=data.get("address", ""),
    )
    _save(row)
    return row


@transaction.atomic
def update_property(
    *,
    actor: Membership,
    raw_id: str,
    data: dict[str, Any],
) -> Property:
    ensure_can_manage_properties(actor)
    row = _property(actor.workspace_id, raw_id)
    if "name" in data:
        row.name = data["name"]
    if "address" in data:
        row.address = data["address"]
    _save(row)
    return row


@transaction.atomic
def delete_property(*, actor: Membership, raw_id: str) -> None:
    ensure_can_manage_properties(actor)
    _discard(_property(actor.workspace_id, raw_id))


def list_buildings(
    actor: Membership,
    *,
    property_id: uuid.UUID | None,
) -> QuerySet[Building]:
    ensure_can_view_properties(actor)
    if property_id is not None:
        _property(actor.workspace_id, property_id)
    rows = Building.objects.filter(workspace_id=actor.workspace_id)
    if property_id is not None:
        rows = rows.filter(property_id=property_id)
    return rows


def get_building(actor: Membership, raw_id: str) -> Building:
    ensure_can_view_properties(actor)
    return _building(actor.workspace_id, raw_id)


@transaction.atomic
def create_building(*, actor: Membership, data: dict[str, Any]) -> Building:
    ensure_can_manage_properties(actor)
    prop = _property(actor.workspace_id, data["property_id"])
    row = Building(
        workspace=actor.workspace,
        property=prop,
        name=data["name"],
    )
    _save(row)
    return row


@transaction.atomic
def update_building(
    *,
    actor: Membership,
    raw_id: str,
    data: dict[str, Any],
) -> Building:
    ensure_can_manage_properties(actor)
    row = (
        Building.objects.select_for_update()
        .filter(workspace_id=actor.workspace_id, id=_parse_id(raw_id))
        .first()
    )
    if row is None:
        raise NotFound()
    if "property_id" in data:
        row.property = _property(actor.workspace_id, data["property_id"])
    if "name" in data:
        row.name = data["name"]
    _save(row)
    return row


@transaction.atomic
def delete_building(*, actor: Membership, raw_id: str) -> None:
    ensure_can_manage_properties(actor)
    _discard(_building(actor.workspace_id, raw_id))


def list_floors(
    actor: Membership,
    *,
    property_id: uuid.UUID | None,
    building_id: uuid.UUID | None,
) -> QuerySet[Floor]:
    ensure_can_view_properties(actor)
    if property_id is not None:
        _property(actor.workspace_id, property_id)
    if building_id is not None:
        _building(actor.workspace_id, building_id)
    rows = Floor.objects.filter(workspace_id=actor.workspace_id)
    if property_id is not None:
        rows = rows.filter(property_id=property_id)
    if building_id is not None:
        rows = rows.filter(building_id=building_id)
    return rows


def get_floor(actor: Membership, raw_id: str) -> Floor:
    ensure_can_view_properties(actor)
    return _floor(actor.workspace_id, raw_id)


@transaction.atomic
def create_floor(*, actor: Membership, data: dict[str, Any]) -> Floor:
    ensure_can_manage_properties(actor)
    prop = _property(actor.workspace_id, data["property_id"])
    building = _building_on_property(
        actor.workspace_id,
        prop.id,
        data.get("building_id"),
    )
    row = Floor(
        workspace=actor.workspace,
        property=prop,
        building=building,
        name=data["name"],
    )
    _save(row)
    return row


@transaction.atomic
def update_floor(
    *,
    actor: Membership,
    raw_id: str,
    data: dict[str, Any],
) -> Floor:
    ensure_can_manage_properties(actor)
    row = (
        Floor.objects.select_for_update()
        .filter(workspace_id=actor.workspace_id, id=_parse_id(raw_id))
        .first()
    )
    if row is None:
        raise NotFound()
    property_id = row.property_id
    if "property_id" in data:
        property_id = _property(actor.workspace_id, data["property_id"]).id
        row.property_id = property_id
    building_id = row.building_id
    if "building_id" in data:
        building = _building_on_property(
            actor.workspace_id,
            property_id,
            data["building_id"],
        )
        building_id = building.id if building is not None else None
        row.building_id = building_id
    elif row.building_id is not None and "property_id" in data:
        _building_on_property(actor.workspace_id, property_id, row.building_id)
    if "name" in data:
        row.name = data["name"]
    _save(row)
    return row


@transaction.atomic
def delete_floor(*, actor: Membership, raw_id: str) -> None:
    ensure_can_manage_properties(actor)
    _discard(_floor(actor.workspace_id, raw_id))


def list_spaces(
    actor: Membership,
    *,
    property_id: uuid.UUID | None,
    building_id: uuid.UUID | None,
    floor_id: uuid.UUID | None,
) -> QuerySet[Space]:
    ensure_can_view_properties(actor)
    if property_id is not None:
        _property(actor.workspace_id, property_id)
    if building_id is not None:
        _building(actor.workspace_id, building_id)
    if floor_id is not None:
        _floor(actor.workspace_id, floor_id)
    rows = Space.objects.filter(workspace_id=actor.workspace_id)
    if property_id is not None:
        rows = rows.filter(property_id=property_id)
    if building_id is not None:
        rows = rows.filter(building_id=building_id)
    if floor_id is not None:
        rows = rows.filter(floor_id=floor_id)
    return rows


def get_space(actor: Membership, raw_id: str) -> Space:
    ensure_can_view_properties(actor)
    return _space(actor.workspace_id, raw_id)


def _apply_place(
    row: Space,
    *,
    workspace_id: uuid.UUID,
    property_id: uuid.UUID,
    building_id: uuid.UUID | None,
    floor_id: uuid.UUID | None,
) -> None:
    prop = _property(workspace_id, property_id)
    building = _building_on_property(workspace_id, prop.id, building_id)
    floor = _floor_on_property(
        workspace_id,
        prop.id,
        floor_id,
        building.id if building is not None else None,
    )
    row.property = prop
    row.building = building
    row.floor = floor


def _merged_block(
    current_availability: str,
    current_reason: str,
    data: dict[str, Any],
) -> tuple[str, str]:
    availability = str(data.get("availability", current_availability))
    if "block_reason" in data:
        block_reason = str(data["block_reason"])
    elif "availability" in data and availability != Space.Availability.UNAVAILABLE:
        block_reason = ""
    else:
        block_reason = current_reason
    _require_block(availability, block_reason)
    return availability, block_reason


@transaction.atomic
def create_space(*, actor: Membership, data: dict[str, Any]) -> Space:
    ensure_can_manage_properties(actor)
    availability, block_reason = _merged_block(
        Space.Availability.ACTIVE,
        "",
        data,
    )
    row = Space(
        workspace=actor.workspace,
        name=data["name"],
        kind=data["kind"],
        availability=availability,
        block_reason=block_reason,
    )
    _apply_place(
        row,
        workspace_id=actor.workspace_id,
        property_id=data["property_id"],
        building_id=data.get("building_id"),
        floor_id=data.get("floor_id"),
    )
    _save(row)
    return row


@transaction.atomic
def update_space(
    *,
    actor: Membership,
    raw_id: str,
    data: dict[str, Any],
) -> Space:
    ensure_can_manage_properties(actor)
    row = (
        Space.objects.select_for_update()
        .filter(workspace_id=actor.workspace_id, id=_parse_id(raw_id))
        .first()
    )
    if row is None:
        raise NotFound()
    if "name" in data:
        row.name = data["name"]
    if "kind" in data:
        row.kind = data["kind"]
    if row.kind == Space.Kind.UNIT and row.beds.exists():
        raise ValidationError(
            {"kind": "Remove the beds before marking this space as a whole unit."}
        )
    availability, block_reason = _merged_block(
        row.availability,
        row.block_reason,
        data,
    )
    row.availability = availability
    row.block_reason = block_reason
    property_id = data.get("property_id", row.property_id)
    building_id = data.get("building_id", row.building_id)
    floor_id = data.get("floor_id", row.floor_id)
    _apply_place(
        row,
        workspace_id=actor.workspace_id,
        property_id=property_id,
        building_id=building_id,
        floor_id=floor_id,
    )
    _save(row)
    return row


@transaction.atomic
def delete_space(*, actor: Membership, raw_id: str) -> None:
    ensure_can_manage_properties(actor)
    _discard(_space(actor.workspace_id, raw_id))


def list_beds(
    actor: Membership,
    *,
    space_id: uuid.UUID | None,
) -> QuerySet[Bed]:
    ensure_can_view_properties(actor)
    if space_id is not None:
        _space(actor.workspace_id, space_id)
    rows = Bed.objects.filter(workspace_id=actor.workspace_id)
    if space_id is not None:
        rows = rows.filter(space_id=space_id)
    return rows


def get_bed(actor: Membership, raw_id: str) -> Bed:
    ensure_can_view_properties(actor)
    row = Bed.objects.filter(
        workspace_id=actor.workspace_id,
        id=_parse_id(raw_id),
    ).first()
    if row is None:
        raise NotFound()
    return row


def _room_for_bed(workspace_id: uuid.UUID, raw: str | uuid.UUID) -> Space:
    row = (
        Space.objects.select_for_update()
        .filter(workspace_id=workspace_id, id=_parse_id(raw))
        .first()
    )
    if row is None:
        raise NotFound()
    if row.kind != Space.Kind.ROOM:
        raise ValidationError(
            {"space_id": "Beds belong to a room. A whole unit does not have beds."}
        )
    return row


@transaction.atomic
def create_bed(*, actor: Membership, data: dict[str, Any]) -> Bed:
    ensure_can_manage_properties(actor)
    space = _room_for_bed(actor.workspace_id, data["space_id"])
    availability, block_reason = _merged_block(
        Space.Availability.ACTIVE,
        "",
        data,
    )
    row = Bed(
        workspace=actor.workspace,
        space=space,
        name=data["name"],
        availability=availability,
        block_reason=block_reason,
    )
    _save(row)
    from tenancies.services import sync_bed_created

    sync_bed_created(row)
    return row


@transaction.atomic
def update_bed(
    *,
    actor: Membership,
    raw_id: str,
    data: dict[str, Any],
) -> Bed:
    ensure_can_manage_properties(actor)
    row = Bed.objects.filter(
        workspace_id=actor.workspace_id,
        id=_parse_id(raw_id),
    ).first()
    if row is None:
        raise NotFound()
    previous_space_id = row.space_id
    next_space: Space | None = None
    if "space_id" in data:
        next_space = Space.objects.filter(
            workspace_id=actor.workspace_id,
            id=_parse_id(data["space_id"]),
        ).first()
        if next_space is None:
            raise NotFound()
    from tenancies.inventory import lock_spaces

    lock_ids = [previous_space_id]
    if next_space is not None:
        lock_ids.append(next_space.id)
    lock_spaces(lock_ids)
    row = (
        Bed.objects.select_for_update()
        .filter(workspace_id=actor.workspace_id, id=row.id)
        .first()
    )
    if row is None:
        raise NotFound()
    if next_space is not None:
        if next_space.kind != Space.Kind.ROOM:
            raise ValidationError(
                {
                    "space_id": (
                        "Beds belong to a room. A whole unit does not have beds."
                    )
                }
            )
        row.space = next_space
    elif row.space.kind != Space.Kind.ROOM:
        raise ValidationError(
            {"space_id": "Beds belong to a room. A whole unit does not have beds."}
        )
    if "name" in data:
        row.name = data["name"]
    availability, block_reason = _merged_block(
        row.availability,
        row.block_reason,
        data,
    )
    row.availability = availability
    row.block_reason = block_reason
    _save(row)
    if next_space is not None and next_space.id != previous_space_id:
        from tenancies.services import sync_bed_moved

        sync_bed_moved(row)
    return row


@transaction.atomic
def delete_bed(*, actor: Membership, raw_id: str) -> None:
    ensure_can_manage_properties(actor)
    bed = Bed.objects.filter(
        workspace_id=actor.workspace_id,
        id=_parse_id(raw_id),
    ).first()
    if bed is None:
        raise NotFound()
    from tenancies.inventory import lock_spaces

    lock_spaces([bed.space_id])
    _discard(bed)
