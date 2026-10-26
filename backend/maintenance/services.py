"""File and update maintenance requests. Availability is not changed here."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from rest_framework.exceptions import NotFound, ValidationError

from accounts.models import User
from maintenance.models import MaintenanceRequest, MaintenanceUpdate, RequestCounter
from maintenance.permissions import (
    ASSIGNABLE_ROLES,
    TRIAGE_ROLES,
    ensure_can_file,
    ensure_can_read,
    ensure_can_update,
)
from organizations.access import parse_uuid
from organizations.models import AuditEvent, Membership, Workspace
from properties.models import Bed, Property, Space
from residents.models import Resident
from tenancies.models import Assignment

BLOCKING = (Assignment.Status.CONFIRMED, Assignment.Status.ACTIVE)
_MAINTENANCE_MOVES = {
    ("open", "cancelled"),
    ("assigned", "in_progress"),
    ("assigned", "cancelled"),
    ("in_progress", "completed"),
    ("in_progress", "cancelled"),
}
_TRIAGE_MOVES = _MAINTENANCE_MOVES | {
    ("open", "assigned"),
    ("open", "in_progress"),
    ("assigned", "open"),
}


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
    parsed = parse_uuid(str(raw))
    if parsed is None:
        raise NotFound()
    return parsed


def _audit(actor: Membership, action: str, request_id: uuid.UUID) -> None:
    AuditEvent.objects.create(
        workspace=actor.workspace,
        actor=actor.user,
        action=action,
        target_type="maintenance_request",
        target_id=request_id,
    )


def _save_request(row: MaintenanceRequest) -> None:
    try:
        row.save()
    except DjangoValidationError as exc:
        raise _as_drf(exc) from exc


def _visible(actor: Membership) -> QuerySet[MaintenanceRequest]:
    """Maintenance staff do not see another person's queue.

    They see requests assigned to them, and requests they filed that nobody
    has taken yet. Everyone else who may read sees the workspace, except a
    resident, who sees the profile linked to their login.
    """
    rows = MaintenanceRequest.objects.filter(workspace_id=actor.workspace_id)
    if actor.role == Membership.Role.RESIDENT:
        return rows.filter(resident__user_id=actor.user_id)
    if actor.role == Membership.Role.MAINTENANCE:
        return rows.filter(
            Q(assignee_id=actor.user_id)
            | Q(assignee__isnull=True, reported_by_id=actor.user_id)
        )
    return rows


def _list_queryset(actor: Membership) -> QuerySet[MaintenanceRequest]:
    return (
        _visible(actor)
        .select_related(
            "property",
            "space",
            "bed",
            "resident",
            "assignee",
            "reported_by",
        )
        .prefetch_related("updates", "updates__actor")
    )


def visible_request_rows(actor: Membership) -> QuerySet[MaintenanceRequest]:
    """Rows this member may count. Maintenance staff do not see the full queue."""
    ensure_can_read(actor)
    return _visible(actor)


def list_requests(
    actor: Membership,
    *,
    status: str | None,
    priority: str | None,
) -> QuerySet[MaintenanceRequest]:
    ensure_can_read(actor)
    rows = _list_queryset(actor)
    if status:
        if status not in MaintenanceRequest.Status.values:
            raise ValidationError({"status": "Choose a status."})
        rows = rows.filter(status=status)
    if priority:
        if priority not in MaintenanceRequest.Priority.values:
            raise ValidationError({"priority": "Choose a priority."})
        rows = rows.filter(priority=priority)
    return rows


def get_request(actor: Membership, raw_id: str) -> MaintenanceRequest:
    ensure_can_read(actor)
    row = _list_queryset(actor).filter(id=_parse_id(raw_id)).first()
    if row is None:
        raise NotFound()
    return row


def _lock_visible(actor: Membership, raw_id: str) -> MaintenanceRequest:
    row = _visible(actor).select_for_update().filter(id=_parse_id(raw_id)).first()
    if row is None:
        raise NotFound()
    return row


def _linked_resident(actor: Membership) -> Resident:
    row = Resident.objects.filter(
        workspace_id=actor.workspace_id,
        user_id=actor.user_id,
    ).first()
    if row is None:
        raise ValidationError(
            {"resident_id": "Your login is not linked to a resident profile."}
        )
    return row


def _staff_resident(actor: Membership, raw: object) -> Resident | None:
    if raw is None or raw == "":
        return None
    if not isinstance(raw, (str, uuid.UUID)):
        raise NotFound()
    row = Resident.objects.filter(
        workspace_id=actor.workspace_id,
        id=_parse_id(raw),
    ).first()
    if row is None:
        raise NotFound()
    return row


def _assignee(actor: Membership, raw: object) -> User:
    if not isinstance(raw, (str, uuid.UUID)):
        raise ValidationError(
            {
                "assignee_id": (
                    "Choose an owner, property manager, or maintenance "
                    "staff member in this workspace."
                )
            }
        )
    membership = (
        Membership.objects.select_related("user")
        .filter(
            workspace_id=actor.workspace_id,
            user_id=_parse_id(raw),
            is_active=True,
            role__in=ASSIGNABLE_ROLES,
        )
        .first()
    )
    if membership is None:
        raise ValidationError(
            {
                "assignee_id": (
                    "Choose an owner, property manager, or maintenance "
                    "staff member in this workspace."
                )
            }
        )
    return membership.user


def _property(actor: Membership, raw: object) -> Property:
    if not isinstance(raw, (str, uuid.UUID)):
        raise NotFound()
    row = Property.objects.filter(
        workspace_id=actor.workspace_id,
        id=_parse_id(raw),
    ).first()
    if row is None:
        raise NotFound()
    return row


def _space(actor: Membership, raw: object) -> Space:
    if not isinstance(raw, (str, uuid.UUID)):
        raise NotFound()
    row = (
        Space.objects.select_related("property")
        .filter(
            workspace_id=actor.workspace_id,
            id=_parse_id(raw),
        )
        .first()
    )
    if row is None:
        raise NotFound()
    return row


def _bed(actor: Membership, raw: object) -> Bed:
    if not isinstance(raw, (str, uuid.UUID)):
        raise NotFound()
    row = Bed.objects.filter(
        workspace_id=actor.workspace_id,
        id=_parse_id(raw),
    ).first()
    if row is None:
        raise NotFound()
    return row


def _resident_place(
    actor: Membership,
    resident: Resident,
    data: dict[str, Any],
) -> tuple[Property | None, Space | None, Bed | None]:
    property_id = data.get("property_id")
    space_id = data.get("space_id")
    bed_id = data.get("bed_id")
    if property_id is None and space_id is None and bed_id is None:
        return None, None, None
    if space_id is None:
        raise ValidationError({"space_id": "Choose a space on your stay."})
    space = _space(actor, space_id)
    stays = Assignment.objects.filter(
        workspace_id=actor.workspace_id,
        resident_id=resident.id,
        space_id=space.id,
        status__in=BLOCKING,
    )
    if not stays.exists():
        raise NotFound()
    bed = None
    if bed_id is not None:
        bed = _bed(actor, bed_id)
        if bed.space_id != space.id:
            raise NotFound()
        whole = stays.filter(bed__isnull=True).exists()
        own_bed = stays.filter(bed_id=bed.id).exists()
        if not whole and not own_bed:
            raise NotFound()
    if property_id is not None and _parse_id(property_id) != space.property_id:
        raise ValidationError({"property_id": "Choose the property for that space."})
    return space.property, space, bed


def _staff_place(
    actor: Membership,
    data: dict[str, Any],
) -> tuple[Property, Space | None, Bed | None]:
    if data.get("property_id") is None:
        raise ValidationError({"property_id": "Choose a property."})
    chosen = _property(actor, data["property_id"])
    space = None
    bed = None
    if data.get("space_id") is not None:
        space = _space(actor, data["space_id"])
        if space.property_id != chosen.id:
            raise ValidationError({"space_id": "Choose a space on this property."})
    if data.get("bed_id") is not None:
        if space is None:
            raise ValidationError({"bed_id": "Choose a space before a bed."})
        bed = _bed(actor, data["bed_id"])
        if bed.space_id != space.id:
            raise ValidationError({"bed_id": "Choose a bed in this space."})
    return chosen, space, bed


def _next_reference(workspace: Workspace) -> str:
    counter, _created = RequestCounter.objects.get_or_create(workspace=workspace)
    number = counter.next_number
    counter.next_number = number + 1
    counter.save(update_fields=["next_number"])
    return f"MNT-{number:04d}"


def _history(
    *,
    actor: Membership,
    row: MaintenanceRequest,
    status_before: str,
    note: str,
    cost: Decimal | None,
) -> None:
    fields: dict[str, Any] = {
        "workspace": actor.workspace,
        "request": row,
        "actor": actor.user,
        "status_before": status_before,
        "status_after": row.status,
        "note": note,
        "assignee": row.assignee,
    }
    if cost is not None:
        fields["cost_amount"] = cost
    MaintenanceUpdate.objects.create(**fields)


def _reject_resident_controls(data: dict[str, Any]) -> None:
    for key in ("assignee_id", "cost_amount", "status", "completion_note"):
        if key in data:
            raise ValidationError({key: "You can file a request. Staff update it."})


@transaction.atomic
def create_request(*, actor: Membership, data: dict[str, Any]) -> MaintenanceRequest:
    ensure_can_file(actor)
    workspace = (
        Workspace.objects.select_for_update().filter(id=actor.workspace_id).first()
    )
    if workspace is None:
        raise NotFound()
    if "status" in data:
        raise ValidationError({"status": "The server sets the status."})
    if "cost_amount" in data:
        raise ValidationError(
            {"cost_amount": "Record a cost when you update the request."}
        )
    if "completion_note" in data:
        raise ValidationError(
            {"completion_note": "Add a completion note when the work is finished."}
        )
    chosen_resident: Resident | None
    chosen_property: Property | None
    space: Space | None
    bed: Bed | None
    if actor.role == Membership.Role.RESIDENT:
        _reject_resident_controls(data)
        linked = _linked_resident(actor)
        supplied = data.get("resident_id")
        if supplied is not None and _parse_id(supplied) != linked.id:
            raise NotFound()
        chosen_resident = linked
        chosen_property, space, bed = _resident_place(actor, linked, data)
    else:
        chosen_resident = _staff_resident(actor, data.get("resident_id"))
        chosen_property, space, bed = _staff_place(actor, data)
    assignee = None
    status = MaintenanceRequest.Status.OPEN
    if data.get("assignee_id") is not None:
        if actor.role not in TRIAGE_ROLES:
            raise ValidationError(
                {
                    "assignee_id": (
                        "Only an owner or property manager can assign a request."
                    )
                }
            )
        assignee = _assignee(actor, data["assignee_id"])
        status = MaintenanceRequest.Status.ASSIGNED
    row = MaintenanceRequest(
        workspace=workspace,
        property=chosen_property,
        space=space,
        bed=bed,
        resident=chosen_resident,
        reported_by=actor.user,
        assignee=assignee,
        reference=_next_reference(workspace),
        description=str(data["description"]),
        priority=str(data["priority"]),
        status=status,
        currency_code=workspace.currency_code,
    )
    _save_request(row)
    _history(actor=actor, row=row, status_before="", note="Request opened.", cost=None)
    _audit(actor, AuditEvent.Action.MAINTENANCE_CREATED, row.id)
    if assignee is not None:
        _audit(actor, AuditEvent.Action.MAINTENANCE_ASSIGNED, row.id)
    return get_request(actor, str(row.id))


def _apply_transition(
    actor: Membership,
    current: str,
    new_status: str,
) -> None:
    if current == new_status:
        return
    allowed = _TRIAGE_MOVES if actor.role in TRIAGE_ROLES else _MAINTENANCE_MOVES
    if (current, new_status) not in allowed:
        raise ValidationError({"status": "That status change is not allowed."})


@transaction.atomic
def update_request(
    *,
    actor: Membership,
    raw_id: str,
    data: dict[str, Any],
) -> MaintenanceRequest:
    Workspace.objects.select_for_update().filter(id=actor.workspace_id).first()
    row = _lock_visible(actor, raw_id)
    ensure_can_update(actor)
    if actor.role == Membership.Role.MAINTENANCE:
        blocked = set(data).difference(
            {"status", "note", "completion_note", "cost_amount"}
        )
        if blocked:
            field = sorted(blocked)[0]
            raise ValidationError(
                {field: ("You can update the status, note, completion note, and cost.")}
            )
    status_before = row.status
    new_status = str(data["status"]) if "status" in data else row.status
    new_assignee = row.assignee
    if "assignee_id" in data:
        if data["assignee_id"] is None:
            new_assignee = None
        else:
            new_assignee = _assignee(actor, data["assignee_id"])
        if "status" not in data:
            if (
                new_assignee is None
                and row.status == MaintenanceRequest.Status.ASSIGNED
            ):
                new_status = MaintenanceRequest.Status.OPEN
            elif (
                new_assignee is not None
                and row.status == MaintenanceRequest.Status.OPEN
            ):
                new_status = MaintenanceRequest.Status.ASSIGNED
    _apply_transition(actor, row.status, new_status)
    if new_status == MaintenanceRequest.Status.OPEN:
        new_assignee = None
    if (
        new_status
        in {
            MaintenanceRequest.Status.ASSIGNED,
            MaintenanceRequest.Status.IN_PROGRESS,
            MaintenanceRequest.Status.COMPLETED,
        }
        and new_assignee is None
    ):
        raise ValidationError({"assignee_id": "Choose an assignee."})
    completion = row.completion_note
    if "completion_note" in data:
        completion = str(data["completion_note"]).strip()
    if new_status == MaintenanceRequest.Status.COMPLETED and not completion:
        raise ValidationError({"completion_note": "Add a completion note."})
    description = row.description
    if "description" in data:
        description = str(data["description"]).strip()
    priority = str(data["priority"]) if "priority" in data else row.priority
    cost = row.cost_amount
    cost_changed = False
    if "cost_amount" in data:
        cost = data["cost_amount"]
        if not isinstance(cost, Decimal):
            raise ValidationError(
                {"cost_amount": "Enter an amount as a decimal string."}
            )
        if cost < 0:
            raise ValidationError(
                {"cost_amount": "Enter a cost that is zero or greater."}
            )
        cost_changed = cost != row.cost_amount
    note_parts: list[str] = []
    if "note" in data and str(data["note"]).strip():
        note_parts.append(str(data["note"]).strip())
    if priority != row.priority:
        note_parts.append(f"Priority set to {priority}.")
    if description != row.description:
        note_parts.append("Description updated.")
    assignee_changed = getattr(new_assignee, "id", None) != row.assignee_id
    status_changed = new_status != status_before
    if not any(
        (
            note_parts,
            cost_changed,
            assignee_changed,
            status_changed,
            completion != row.completion_note,
        )
    ):
        raise ValidationError("Provide a field to change.")
    if completion != row.completion_note and "completion_note" in data:
        note_parts.append("Completion note updated.")
    row.description = description
    row.priority = priority
    row.status = new_status
    row.assignee = new_assignee
    row.completion_note = completion
    row.cost_amount = cost
    _save_request(row)
    _history(
        actor=actor,
        row=row,
        status_before=status_before,
        note=" ".join(note_parts),
        cost=cost if cost_changed else None,
    )
    if status_changed:
        _audit(actor, AuditEvent.Action.MAINTENANCE_STATUS_CHANGED, row.id)
    if assignee_changed:
        _audit(actor, AuditEvent.Action.MAINTENANCE_ASSIGNED, row.id)
    if cost_changed:
        _audit(actor, AuditEvent.Action.MAINTENANCE_COST_RECORDED, row.id)
    return get_request(actor, str(row.id))
