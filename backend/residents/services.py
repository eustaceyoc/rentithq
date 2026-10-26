"""Resident profiles. The active membership chooses the workspace."""

from __future__ import annotations

import uuid
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from rest_framework.exceptions import NotFound, ValidationError

from accounts.models import User
from organizations.access import parse_uuid
from organizations.models import AuditEvent, Membership
from residents.models import Resident
from residents.permissions import ensure_can_read_occupancy, ensure_can_write_occupancy


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


def _contact_email(value: str) -> str:
    text = value.strip().lower()
    if not text:
        return ""
    try:
        validate_email(text)
    except DjangoValidationError as exc:
        raise ValidationError({"email": "Enter a valid email address."}) from exc
    return text


def _account(actor: Membership, email: str) -> User | None:
    text = email.strip()
    if not text:
        return None
    try:
        normalized = User.objects.normalize_user_email(text)
    except ValueError as exc:
        raise ValidationError(
            {"account_email": "Enter a valid email address."}
        ) from exc
    user = User.objects.filter(email=normalized, is_active=True).first()
    member = False
    if user is not None:
        member = Membership.objects.filter(
            workspace_id=actor.workspace_id,
            user=user,
            role=Membership.Role.RESIDENT,
            is_active=True,
        ).exists()
    if user is None or not member:
        raise ValidationError(
            {"account_email": "No resident membership uses that email."}
        )
    return user


def _visible(actor: Membership) -> QuerySet[Resident]:
    ensure_can_read_occupancy(actor)
    rows = Resident.objects.select_related("user").filter(
        workspace_id=actor.workspace_id
    )
    if actor.role == Membership.Role.RESIDENT:
        rows = rows.filter(user_id=actor.user_id)
    return rows


def list_residents(actor: Membership) -> QuerySet[Resident]:
    return _visible(actor)


def get_resident(actor: Membership, raw_id: str) -> Resident:
    row = _visible(actor).filter(id=_parse_id(raw_id)).first()
    if row is None:
        raise NotFound()
    return row


def _audit(actor: Membership, action: str, resident_id: uuid.UUID) -> None:
    AuditEvent.objects.create(
        workspace=actor.workspace,
        actor=actor.user,
        action=action,
        target_type="resident",
        target_id=resident_id,
    )


def _save(row: Resident) -> None:
    try:
        row.save()
    except DjangoValidationError as exc:
        raise _as_drf(exc) from exc
    except IntegrityError as exc:
        if "resident_one_login" in str(exc):
            raise ValidationError(
                {"account_email": "That account is already linked to a resident."}
            ) from exc
        raise


@transaction.atomic
def create_resident(*, actor: Membership, data: dict[str, Any]) -> Resident:
    ensure_can_write_occupancy(actor)
    row = Resident(
        workspace=actor.workspace,
        user=_account(actor, data.get("account_email", "")),
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=_contact_email(data.get("email", "")),
        phone=data.get("phone", ""),
    )
    _save(row)
    return row


def _lock_resident(actor: Membership, raw_id: str, *, own: bool) -> Resident:
    rows = Resident.objects.select_for_update().filter(
        workspace_id=actor.workspace_id,
        id=_parse_id(raw_id),
    )
    if own:
        rows = rows.filter(user_id=actor.user_id)
    row = rows.first()
    if row is None:
        raise NotFound()
    return row


def _apply_own_contact(row: Resident, data: dict[str, Any]) -> list[str]:
    blocked = set(data).difference({"phone", "email"})
    if blocked:
        field = sorted(blocked)[0]
        raise ValidationError({field: "You can change only your phone and email."})
    if "phone" not in data and "email" not in data:
        raise ValidationError("Provide a field to change.")
    changed: list[str] = []
    if "phone" in data:
        phone = str(data["phone"]).strip()
        if phone != row.phone:
            row.phone = phone
            changed.append(AuditEvent.Action.RESIDENT_PHONE_UPDATED)
    if "email" in data:
        email = _contact_email(str(data["email"]))
        if email != row.email:
            row.email = email
            changed.append(AuditEvent.Action.RESIDENT_EMAIL_UPDATED)
    return changed


@transaction.atomic
def update_resident(
    *,
    actor: Membership,
    raw_id: str,
    data: dict[str, Any],
) -> Resident:
    if actor.role == Membership.Role.RESIDENT:
        row = _lock_resident(actor, raw_id, own=True)
        changed = _apply_own_contact(row, data)
        if changed:
            _save(row)
            for action in changed:
                _audit(actor, action, row.id)
        return row
    ensure_can_write_occupancy(actor)
    row = _lock_resident(actor, raw_id, own=False)
    if "first_name" in data:
        row.first_name = data["first_name"]
    if "last_name" in data:
        row.last_name = data["last_name"]
    if "email" in data:
        row.email = _contact_email(data["email"])
    if "phone" in data:
        row.phone = data["phone"]
    if "account_email" in data:
        row.user = _account(actor, data["account_email"])
    _save(row)
    return row


@transaction.atomic
def delete_resident(*, actor: Membership, raw_id: str) -> None:
    ensure_can_write_occupancy(actor)
    row = Resident.objects.filter(
        workspace_id=actor.workspace_id, id=_parse_id(raw_id)
    ).first()
    if row is None:
        raise NotFound()
    if (
        row.bookings.exists()
        or row.tenancies.exists()
        or row.assignments.exists()
        or row.invoices.exists()
        or row.payments.exists()
        or row.maintenance_requests.exists()
    ):
        raise ValidationError(
            {
                "detail": (
                    "This resident has occupancy or billing history "
                    "or a maintenance request and was not deleted."
                )
            }
        )
    row.delete()
