"""Workspace and membership changes. Callers are already authenticated."""

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.models import User
from organizations.models import AuditEvent, Membership, Workspace


def _audit(
    *,
    workspace: Workspace | None,
    actor: User | None,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
) -> None:
    AuditEvent.objects.create(
        workspace=workspace,
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
    )


def _has_billing(workspace: Workspace) -> bool:
    from billing.models import Invoice, Payment

    return (
        Invoice.objects.filter(workspace=workspace).exists()
        or Payment.objects.filter(workspace=workspace).exists()
    )


def _require_owner(actor: Membership, workspace: Workspace) -> None:
    if (
        not actor.is_active
        or actor.role != Membership.Role.OWNER
        or actor.workspace_id != workspace.id
    ):
        raise PermissionDenied()


def _lock_active_owners(workspace_id: uuid.UUID) -> list[Membership]:
    return list(
        Membership.objects.select_for_update()
        .filter(
            workspace_id=workspace_id,
            role=Membership.Role.OWNER,
            is_active=True,
        )
        .order_by("id")
    )


@transaction.atomic
def create_workspace(
    *,
    owner: User,
    name: str,
    currency_code: str,
    timezone_name: str,
) -> Workspace:
    if not owner.is_active:
        raise PermissionDenied()
    workspace = Workspace(
        name=name,
        currency_code=currency_code,
        timezone=timezone_name,
        status=Workspace.Status.ACTIVE,
    )
    workspace.save()
    membership = Membership(
        workspace=workspace,
        user=owner,
        role=Membership.Role.OWNER,
        is_active=True,
    )
    membership.save()
    _audit(
        workspace=workspace,
        actor=owner,
        action=AuditEvent.Action.WORKSPACE_CREATED,
        target_type="workspace",
        target_id=workspace.id,
    )
    _audit(
        workspace=workspace,
        actor=owner,
        action=AuditEvent.Action.MEMBERSHIP_CREATED,
        target_type="membership",
        target_id=membership.id,
    )
    return workspace


@transaction.atomic
def update_workspace(
    *,
    actor: Membership,
    workspace: Workspace,
    changes: dict[str, str],
) -> Workspace:
    _require_owner(actor, workspace)
    if "name" in changes:
        workspace.name = changes["name"]
    if "currency_code" in changes:
        from organizations.validation import currency_code_or_error

        try:
            next_code: str | None = currency_code_or_error(changes["currency_code"])
        except DjangoValidationError:
            next_code = None
        if (
            next_code is not None
            and next_code != workspace.currency_code
            and _has_billing(workspace)
        ):
            raise ValidationError(
                {
                    "currency_code": (
                        "The currency cannot change after an invoice "
                        "or payment is recorded."
                    )
                }
            )
        workspace.currency_code = changes["currency_code"]
    if "timezone" in changes:
        workspace.timezone = changes["timezone"]
    workspace.save()
    _audit(
        workspace=workspace,
        actor=actor.user,
        action=AuditEvent.Action.WORKSPACE_UPDATED,
        target_type="workspace",
        target_id=workspace.id,
    )
    return workspace


@transaction.atomic
def delete_workspace(*, actor: Membership, workspace: Workspace) -> None:
    _require_owner(actor, workspace)
    _audit(
        workspace=workspace,
        actor=actor.user,
        action=AuditEvent.Action.WORKSPACE_DELETED,
        target_type="workspace",
        target_id=workspace.id,
    )
    try:
        workspace.delete()
    except ProtectedError as exc:
        raise ValidationError(
            {
                "detail": (
                    "This workspace still has occupancy history or billing history "
                    "or a maintenance request. "
                    "Delete is blocked so that history is kept."
                )
            }
        ) from exc


@transaction.atomic
def add_member(*, actor: Membership, email: str, role: str) -> Membership:
    _require_owner(actor, actor.workspace)
    if role not in Membership.Role.values:
        raise ValidationError({"role": "Choose a valid role."})
    try:
        normalized = User.objects.normalize_user_email(email)
    except ValueError as exc:
        raise ValidationError({"email": "Enter a valid email address."}) from exc
    try:
        user = User.objects.get(email=normalized, is_active=True)
    except User.DoesNotExist as exc:
        raise ValidationError({"email": "No active account uses that email."}) from exc

    existing = (
        Membership.objects.select_for_update()
        .filter(workspace_id=actor.workspace_id, user=user)
        .first()
    )
    if existing is not None and existing.is_active:
        raise ValidationError(
            {"email": "That account is already a member of this workspace."}
        )
    if existing is not None:
        existing.role = role
        existing.is_active = True
        existing.save(update_fields=["role", "is_active", "updated_at"])
        _audit(
            workspace=actor.workspace,
            actor=actor.user,
            action=AuditEvent.Action.MEMBERSHIP_UPDATED,
            target_type="membership",
            target_id=existing.id,
        )
        return existing

    membership = Membership(
        workspace=actor.workspace,
        user=user,
        role=role,
        is_active=True,
    )
    try:
        with transaction.atomic():
            membership.save()
    except IntegrityError as exc:
        raise ValidationError(
            {"email": "That account is already a member of this workspace."}
        ) from exc
    _audit(
        workspace=actor.workspace,
        actor=actor.user,
        action=AuditEvent.Action.MEMBERSHIP_CREATED,
        target_type="membership",
        target_id=membership.id,
    )
    return membership


@transaction.atomic
def change_member_role(
    *, actor: Membership, membership: Membership, role: str
) -> Membership:
    _require_owner(actor, actor.workspace)
    if membership.workspace_id != actor.workspace_id or not membership.is_active:
        raise NotFound()
    if role not in Membership.Role.values:
        raise ValidationError({"role": "Choose a valid role."})
    locked = (
        Membership.objects.select_for_update()
        .filter(pk=membership.pk, workspace_id=actor.workspace_id, is_active=True)
        .first()
    )
    if locked is None:
        raise NotFound()
    owners = _lock_active_owners(actor.workspace_id)
    if (
        locked.role == Membership.Role.OWNER
        and role != Membership.Role.OWNER
        and len(owners) <= 1
    ):
        raise ValidationError({"role": "The workspace must keep an owner."})
    locked.role = role
    locked.save(update_fields=["role", "updated_at"])
    _audit(
        workspace=actor.workspace,
        actor=actor.user,
        action=AuditEvent.Action.MEMBERSHIP_UPDATED,
        target_type="membership",
        target_id=locked.id,
    )
    return locked


@transaction.atomic
def deactivate_member(*, actor: Membership, membership: Membership) -> None:
    _require_owner(actor, actor.workspace)
    if membership.workspace_id != actor.workspace_id or not membership.is_active:
        raise NotFound()
    locked = (
        Membership.objects.select_for_update()
        .filter(pk=membership.pk, workspace_id=actor.workspace_id, is_active=True)
        .first()
    )
    if locked is None:
        raise NotFound()
    owners = _lock_active_owners(actor.workspace_id)
    if locked.role == Membership.Role.OWNER and len(owners) <= 1:
        raise ValidationError({"detail": "The workspace must keep an owner."})
    locked.is_active = False
    locked.save(update_fields=["is_active", "updated_at"])
    _audit(
        workspace=actor.workspace,
        actor=actor.user,
        action=AuditEvent.Action.MEMBERSHIP_DEACTIVATED,
        target_type="membership",
        target_id=locked.id,
    )
